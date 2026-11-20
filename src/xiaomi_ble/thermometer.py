"""Stateful temperature estimate for the MMC-T201 thermometer."""

from collections import deque
from math import isfinite
from statistics import mean, pvariance

_INVALID_READING = {0x7FF0, 0x7FF1, 0x7FF2}
_START_TEMPERATURE = 4.86445 / (2 * 0.07764)


class MMCT201Temperature:
    """Process unencrypted or decrypted MiBeacon temperature samples."""

    def __init__(self, compensation_target: float | None = None) -> None:
        self._compensation_samples: deque[float] = deque(maxlen=15)
        self._compensation_target: float | None = None
        self._reset_compensation()
        self.set_compensation(compensation_target)
        self._last_packet: tuple[int, bytes] | None = None
        self._last_packet_at = float("-inf")
        self._reset_prediction()

    def set_compensation(self, target: float | None) -> None:
        """Set a reference temperature in Celsius, or None to disable."""
        if target is not None and (not isfinite(target) or not 32 <= target <= 42):
            raise ValueError("MMC-T201 compensation target must be 32–42 °C")
        if target != self._compensation_target:
            self._compensation_target = target
            self._reset_compensation()

    def _reset_compensation(self) -> None:
        self._compensation_samples.clear()
        self._compensation_started_at: float | None = None
        self._compensation_offset: float | None = None

    def _reset_prediction(self) -> None:
        self._second_samples: deque[tuple[float, float]] = deque()
        self._smoothed_second: float | None = None
        self._last_prediction = 0.0
        self._prediction_started_at: float | None = None
        self._active = False
        self._warming_up = False
        self._stable_samples = 0
        self._stable_temperature: float | None = None
        self._has_cold_sample = False

    def update(
        self, first_raw: int, second_raw: int, packet: tuple[int, bytes], now: float
    ) -> float | None:
        """Return a body estimate for a new valid sample."""
        if packet == self._last_packet and now - self._last_packet_at < 10:
            return None
        if now - self._last_packet_at > 300:
            self._reset_prediction()
            self._reset_compensation()
        self._last_packet = packet
        self._last_packet_at = now

        first = first_raw / 100
        second = second_raw / 100
        if first_raw in _INVALID_READING or not 0 < first <= 50:
            return None
        if first <= 32:
            self._reset_compensation()
        if first <= 32 and (self._active or not self._has_cold_sample):
            self._reset_prediction()
            self._has_cold_sample = True
        if second_raw in _INVALID_READING or not 0 < second <= 50:
            return None

        if first < 33:
            self._has_cold_sample = True
        smoothed = self._smooth_second(second, now)
        primary = self._predict(first, second, 0.454376, now)
        self._predict(first, smoothed, 0.90594, now)

        if first <= 32:
            return None
        if self._has_cold_sample and self._warming_up and self._stable_samples >= 11:
            primary = self._adjust_stable_temperature(primary, smoothed)
        return self._apply_compensation(primary, now)

    def _predict(
        self, first: float, second: float, coefficient: float, now: float
    ) -> float:
        self._last_prediction = max(self._last_prediction, first)
        if self._active and first <= _START_TEMPERATURE - 0.2:
            self._active = False
        elif not self._active and first >= _START_TEMPERATURE:
            self._active = True
            self._prediction_started_at = now

        prediction = first
        if self._active:
            started_at = self._prediction_started_at
            minimum_difference = (
                1.5 if started_at is not None and int(now - started_at) > 300 else 1.2
            )
            prediction = max(
                first,
                110.97539
                - 4.86445 * first
                + 0.07764 * first * first
                + coefficient * max(first - second, minimum_difference),
            )

        self._last_prediction = min(prediction, self._last_prediction + 0.3)
        return self._last_prediction

    def _smooth_second(self, second: float, now: float) -> float:
        while self._second_samples and self._second_samples[0][0] < now - 300:
            self._second_samples.popleft()
        self._second_samples.append((now, second))
        average = mean(value for _, value in self._second_samples)

        if self._has_cold_sample and second - average > 0.2:
            self._warming_up = True
            self._stable_samples = 11

        previous = self._smoothed_second
        smoothed = average
        if self._warming_up and previous is not None:
            smoothed = min(max(second, previous - 0.05), previous + 0.05)

        if second - average <= 0.2 and self._has_cold_sample:
            if self._warming_up:
                self._warming_up = False
                self._has_cold_sample = False
                self._stable_temperature = None
                self._second_samples.clear()
            elif self._stable_samples < 11:
                self._stable_samples += 1
                if self._stable_samples == 11:
                    self._warming_up = True
                    self._stable_temperature = None
                    self._second_samples.clear()

        self._smoothed_second = smoothed
        return smoothed

    def _adjust_stable_temperature(self, prediction: float, fallback: float) -> float:
        if self._stable_temperature is None:
            self._stable_temperature = prediction
        elif self._second_samples:
            previous = self._stable_temperature
            step = 0.2 if abs(prediction - previous) > 0.2 else 0.05
            self._stable_temperature = min(
                max(prediction, previous - step), previous + step
            )
        else:
            return fallback
        return self._stable_temperature

    def _apply_compensation(self, prediction: float, now: float) -> float:
        if self._compensation_target is None:
            return prediction
        if self._compensation_started_at is None:
            if prediction <= 32:
                return prediction
            self._compensation_started_at = now
        if self._compensation_offset is None:
            self._compensation_samples.append(prediction)
            if (
                now - self._compensation_started_at >= 18 * 60
                and len(self._compensation_samples) == 15
                and pvariance(self._compensation_samples) <= 0.1
            ):
                self._compensation_offset = self._compensation_target - mean(
                    self._compensation_samples
                )
        return prediction + (self._compensation_offset or 0.0)

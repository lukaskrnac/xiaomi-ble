"""Regression tests for the MMC-T201 predictor and compensation."""

import pytest

from xiaomi_ble.thermometer import MMCT201Temperature


def sample(
    thermometer: MMCT201Temperature,
    now: int,
    *,
    first: int = 3700,
    second: int = 3500,
) -> float | None:
    return thermometer.update(first, second, (now % 256, b"test"), now)


def test_uses_shared_predictor_and_rebases_after_a_measurement_gap():
    thermometer = MMCT201Temperature()
    assert sample(thermometer, 0) == pytest.approx(37.3)
    assert sample(thermometer, 0) is None
    assert sample(thermometer, 10) == pytest.approx(37.9)
    assert sample(thermometer, 20) == pytest.approx(38.188652)
    assert sample(thermometer, 400) == pytest.approx(37.3)


def test_compensation_waits_for_time_and_stability_and_resets_when_removed():
    thermometer = MMCT201Temperature(36.5)
    for now in range(0, 990, 10):
        sample(thermometer, now)

    # Make the recent window unstable at the 18-minute mark.
    for now in range(990, 1081, 10):
        result = sample(thermometer, now, first=3800)
    assert result == pytest.approx(39.601578)

    for now in range(1090, 1250, 10):
        result = sample(thermometer, now)
    assert result == pytest.approx(36.5)

    # The offset is fixed for later samples and is cleared when the tag cools.
    assert sample(thermometer, 1250, first=3710) != pytest.approx(36.5)
    assert sample(thermometer, 1260, first=2346, second=0x7FF2) is None
    assert sample(thermometer, 1270) != pytest.approx(36.5)


def test_compensation_target_can_be_changed_or_disabled():
    thermometer = MMCT201Temperature()
    with pytest.raises(ValueError, match="compensation target"):
        thermometer.set_compensation(float("nan"))
    thermometer.set_compensation(36.5)
    for now in range(0, 1081, 10):
        result = sample(thermometer, now)
    assert result == pytest.approx(36.5)

    thermometer.set_compensation(None)
    assert sample(thermometer, 1090) == pytest.approx(38.188652)

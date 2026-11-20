"""Regression tests for the MMC-T201 predictor."""

import pytest

from xiaomi_ble.thermometer import MMCT201Temperature


def sample(
    thermometer: MMCT201Temperature,
    now: int,
    *,
    first: float = 37.0,
    second: float = 35.0,
) -> float | None:
    return thermometer.update(first, second, (now % 256, b"test"), now)


def test_uses_shared_predictor_and_rebases_after_a_measurement_gap():
    thermometer = MMCT201Temperature()
    assert sample(thermometer, 0) == pytest.approx(37.3)
    assert sample(thermometer, 0) is None
    assert sample(thermometer, 10) == pytest.approx(37.9)
    assert sample(thermometer, 20) == pytest.approx(38.188652)
    assert sample(thermometer, 400) == pytest.approx(37.3)

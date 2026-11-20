# MMC-T201 test in Home Assistant

The fork decodes the MMC-T201 MiBeacon device ID `0x00DB`. This includes a
thermometer advertising the name MMC-T201-2 with that same ID. The test override
uses your installed Home Assistant Core version's Xiaomi BLE integration and
the decoding code from your checkout of this fork.

Run this from the fork checkout with Python 3 on any machine that can write to
your Home Assistant configuration folder. On a PC, the folder can be a mounted
share or a local copy from which you transfer `custom_components/xiaomi_ble`.
Use your exact Core version from Settings → About and the correct config path.

```sh
python3 examples/install_ha_test.py 2026.11.2 /config
```

To enable compensation for one thermometer, include its MAC and your selected
reference temperature in Celsius. For example:

```sh
python3 examples/install_ha_test.py 2026.11.2 /config \
  --mac A4:C1:38:4A:15:F8 --target 36.5
```

The installer leaves existing config entries in place and refuses to overwrite
an existing Xiaomi BLE custom integration. Restart Home Assistant and use the
existing Xiaomi BLE device and entities. The ESPHome proxy continues forwarding
the same broadcasts.

For a comparison, log the initial warm-up and readings after the thermometer
stabilizes. Compensation takes at least 18 minutes after the reading first
exceeds 32 °C and also depends on the latest 15 samples passing the stability
check. The reference is configurable in the installed `__init__.py` using
`mmc_t201_compensation_target`. Omit that argument to disable compensation.
Restart Home Assistant after changing it.

To revert, move the installed `custom_components/xiaomi_ble` folder out of
`custom_components` and restart Home Assistant. If you moved an earlier custom
integration aside, restore it before the restart.

## Implementation details

The estimate uses the polynomial and both ordered prediction passes observed
in Miaomiaoce 1.4.2, including the shared increase limiter, time-dependent
minimum difference and second-channel smoothing. The fork omits the small
random perturbations used by the app, uses a per-device sample clock, limits
duplicate broadcasts, resets on a long sample gap and withholds a new body
temperature for invalid channels or a first reading at or below 32 °C. For
an existing sensor, Home Assistant can continue showing its last valid value.
Battery updates remain available. This is an experimental port. Agreement
with the original app requires comparison on the physical thermometer.

Library users can pass `mmc_t201_compensation_target=36.5` to
`XiaomiBluetoothDeviceData`, or set a reference at runtime with
`set_mmc_t201_compensation(36.5)`. Passing `None` disables it.

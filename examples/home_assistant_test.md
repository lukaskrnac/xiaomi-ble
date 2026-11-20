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

The installer leaves existing config entries in place and refuses to overwrite
an existing Xiaomi BLE custom integration. Restart Home Assistant and use the
existing Xiaomi BLE device. The computed temperature is joined by **Temperature
T1** and **Temperature T2**, the two unadjusted values in the BLE packet. Each
invalid channel appears without a numeric reading. The ESPHome proxy continues
forwarding the same broadcasts.

To revert, move the installed `custom_components/xiaomi_ble` folder out of
`custom_components` and restart Home Assistant. If you moved an earlier custom
integration aside, restore it before the restart.

## Implementation details

The estimate uses the polynomial and both ordered prediction passes observed
in Miaomiaoce 1.4.2, including the shared increase limiter, time-dependent
upper limit on T1 − T2 and second-channel smoothing. The fork omits the small
random perturbations used by the app, uses a per-device sample clock, limits
duplicate broadcasts, resets on a long sample gap and withholds a new body
temperature for invalid channels or a first reading at or below 32 °C. For
an existing sensor, Home Assistant can continue showing its last valid value.
Battery updates remain available. This is an experimental port. Agreement
with the original app requires comparison on the physical thermometer.

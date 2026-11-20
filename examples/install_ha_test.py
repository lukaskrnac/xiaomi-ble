"""Prepare a removable Xiaomi BLE override for a matching Home Assistant release."""

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from urllib.request import urlopen

CORE_REPOSITORY = "https://api.github.com/repos/home-assistant/core/contents"
DOMAIN_PATH = "homeassistant/components/xiaomi_ble"


def download(url):
    with urlopen(url, timeout=30) as response:
        return response.read()


def copy_component(version, directory, prefix=DOMAIN_PATH):
    items = json.loads(download(f"{CORE_REPOSITORY}/{prefix}?ref={version}"))
    for item in items:
        target = directory / item["name"]
        if item["type"] == "dir":
            target.mkdir()
            copy_component(version, target, item["path"])
        elif item["type"] == "file":
            target.write_bytes(download(item["download_url"]))


def add_mmc_t201_entities(component):
    """Name the two raw temperature entities in the Home Assistant override."""
    sensor = component / "sensor.py"
    source = sensor.read_text(encoding="utf-8")
    index = "SENSOR_DESCRIPTIONS = {"
    lookup = """device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
            (description.device_class, description.native_unit_of_measurement)
        ]"""
    if source.count(index) != 1 or source.count(lookup) != 1:
        raise RuntimeError("Xiaomi BLE sensor mapping differs in this Core release")
    descriptions = """MMC_T201_SENSOR_DESCRIPTIONS = {
    key: SensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    )
    for key in ("mmc_t201_t1", "mmc_t201_t2")
}

"""
    source = source.replace(index, descriptions + index)
    source = source.replace(
        lookup,
        """device_key_to_bluetooth_entity_key(device_key): (
            MMC_T201_SENSOR_DESCRIPTIONS.get(device_key.key)
            or SENSOR_DESCRIPTIONS[
                (description.device_class, description.native_unit_of_measurement)
            ]
        )""",
    )
    sensor.write_text(source, encoding="utf-8")
    translations = component / "translations"
    translations.mkdir(exist_ok=True)
    for locale, label in (("en", "Temperature"), ("sk", "Teplota")):
        path = translations / f"{locale}.json"
        if path.exists():
            strings = json.loads(path.read_text(encoding="utf-8"))
        elif locale == "en":
            strings = json.loads(
                (component / "strings.json").read_text(encoding="utf-8")
            )
        else:
            strings = {}
        sensors = strings.setdefault("entity", {}).setdefault("sensor", {})
        for channel in (1, 2):
            sensors[f"mmc_t201_t{channel}"] = {"name": f"{label} T{channel}"}
        path.write_text(
            json.dumps(strings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def prepare_component(version, destination):
    library = Path(__file__).resolve().parents[1] / "src" / "xiaomi_ble"
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        component = Path(staging) / "xiaomi_ble"
        component.mkdir()
        copy_component(version, component)

        manifest_file = component / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["version"] = "1.1.0"
        manifest_file.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        for path in component.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            source = re.sub(
                r"(?m)^from xiaomi_ble(?=\s|\.)", "from ._test_library", source
            )
            path.write_text(source, encoding="utf-8")

        add_mmc_t201_entities(component)

        shutil.copytree(
            library,
            component / "_test_library",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        if destination.exists():
            raise FileExistsError(destination)
        component.rename(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Installed Home Assistant Core version")
    parser.add_argument("config", type=Path, help="Home Assistant configuration folder")
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}\.\d{1,2}\.\d+(?:(?:b|rc)\d+)?", args.version):
        parser.error("Use the exact installed Core version, e.g. 2026.11.2.")
    if not (args.config / "configuration.yaml").is_file():
        parser.error("The configuration folder must contain configuration.yaml.")
    destination = args.config / "custom_components" / "xiaomi_ble"
    if destination.exists():
        parser.error(f"{destination} already exists. Move it aside before installing.")
    destination.parent.mkdir(exist_ok=True)
    prepare_component(args.version, destination)
    print(
        f"Prepared {destination}. Restart Home Assistant to load the test integration."
    )


if __name__ == "__main__":
    main()

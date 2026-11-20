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
MAC_PATTERN = r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}"


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


def prepare_component(version, destination, address, target):
    library = Path(__file__).resolve().parents[1] / "src" / "xiaomi_ble"
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        component = Path(staging) / "xiaomi_ble"
        component.mkdir()
        copy_component(version, component)

        manifest_file = component / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["version"] = "1.0.0"
        manifest_file.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        for path in component.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            source = re.sub(
                r"(?m)^from xiaomi_ble(?=\s|\.)", "from ._test_library", source
            )
            path.write_text(source, encoding="utf-8")

        if address is not None:
            init = component / "__init__.py"
            source = init.read_text(encoding="utf-8")
            marker = "    data = XiaomiBluetoothDeviceData(**kwargs)"
            if source.count(marker) != 1:
                raise RuntimeError(
                    "Xiaomi BLE setup differs in this Home Assistant release"
                )
            source = source.replace(
                marker,
                f"    if address.upper() == {address!r}:\n"
                f'        kwargs["mmc_t201_compensation_target"] = {target!r}\n'
                f"{marker}",
            )
            init.write_text(source, encoding="utf-8")

        translations = component / "translations"
        translations.mkdir(exist_ok=True)
        if not (translations / "en.json").exists():
            shutil.copyfile(component / "strings.json", translations / "en.json")

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
    parser.add_argument("--mac", type=str.upper, help="Thermometer Bluetooth address")
    parser.add_argument("--target", type=float, help="Compensation reference in °C")
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}\.\d{1,2}\.\d+(?:(?:b|rc)\d+)?", args.version):
        parser.error("Use the exact installed Core version, e.g. 2026.11.2.")
    if not (args.config / "configuration.yaml").is_file():
        parser.error("The configuration folder must contain configuration.yaml.")
    if (args.mac is None) != (args.target is None):
        parser.error("Provide --mac and --target together to enable compensation.")
    if args.mac is not None and (
        not re.fullmatch(MAC_PATTERN, args.mac) or not 32 <= args.target <= 42
    ):
        parser.error("Enter a MAC address and a reference temperature within 32–42 °C.")
    destination = args.config / "custom_components" / "xiaomi_ble"
    if destination.exists():
        parser.error(f"{destination} already exists. Move it aside before installing.")
    destination.parent.mkdir(exist_ok=True)
    prepare_component(args.version, destination, args.mac, args.target)
    print(
        f"Prepared {destination}. Restart Home Assistant to load the test integration."
    )


if __name__ == "__main__":
    main()

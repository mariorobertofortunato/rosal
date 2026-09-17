"""Acquire target DEX files and dependency markers from the APK."""

import zipfile
from pathlib import Path

def _apk_path(apk=None):
    if not apk:
        raise ValueError("APK path was not provided and APK is not set")

    path = Path(apk).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"APK not found: {path}")
    return path


def extract_target_dex(apk, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(_apk_path(apk)) as archive:
        names = sorted(
            name
            for name in archive.namelist()
            if "/" not in name
            and name.startswith("classes")
            and name.endswith(".dex")
        )
        if not names:
            raise ValueError("APK does not contain classes*.dex")

        paths = []
        for name in names:
            output = destination / Path(name).name
            output.write_bytes(archive.read(name))
            paths.append(output)

    #return paths


def create_markers(apk, markers_file):
    """Write ``META-INF/*.version`` entries as ``name:version`` markers."""
    markers_file = Path(markers_file)
    markers_file.parent.mkdir(parents=True, exist_ok=True)

    markers = []
    with zipfile.ZipFile(_apk_path(apk)) as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith("META-INF/") or not name.endswith(".version"):
                continue

            version = archive.read(name).decode("utf-8").strip()
            if version:
                markers.append(f"{name}:{version}")

    markers_file.write_text(
        "".join(f"{marker}\n" for marker in markers),
        encoding="utf-8",
    )
    #return destination


def main(apk=None, markers_file=None, target_dex_dir=None):
    #work_dir = Path(work_dir).expanduser().resolve()
    extract_target_dex(apk, target_dex_dir)
    create_markers(apk, markers_file)


if __name__ == "__main__":
    main()
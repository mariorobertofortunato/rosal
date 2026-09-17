#!/usr/bin/env python3

import shutil
import subprocess
import sys
import tempfile
import zipfile
import rosal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x


def log(msg):
    tqdm.write(msg)


def parse_marker(line):
    line = line.strip()

    if not line or ":" not in line:
        return None

    marker, version = line.rsplit(":", 1)

    if not marker.startswith("META-INF/"):
        return None

    if not marker.endswith(".version"):
        return None

    raw = marker[
        len("META-INF/"):
        -len(".version")
    ]

    if not raw or not version:
        return None

    return raw, version


def resolve(raw):
    if raw in rosal.OVERRIDES:
        return rosal.OVERRIDES[raw]

    if raw in rosal.VERSION_OVERRIDES:
        return rosal.VERSION_OVERRIDES[raw]

    if raw.startswith("androidx."):
        parts = raw.split("_", 1)

        if len(parts) != 2:
            return None

        return parts[0], parts[1]

    if raw.startswith("com.google.android.material_"):
        return (
            "com.google.android.material",
            raw.split("_", 1)[1],
        )

    parts = raw.rsplit("_", 1)

    if len(parts) != 2:
        return None

    return parts[0], parts[1]


def repo_for(group):
    if (group.startswith("androidx.") or group == "com.google.android.material"):
        return rosal.GOOGLE_MAVEN

    return rosal.MAVEN_CENTRAL


def build_url(repo, group, artifact, version, extension):
    group_path = group.replace(".", "/")

    return (
        f"{repo}/{group_path}/"
        f"{artifact}/{version}/"
        f"{artifact}-{version}.{extension}"
    )


def download(url, destination):
    request = Request(
        url,
        headers={
            "User-Agent": "ROSAL/1.0",
        },
    )

    with urlopen(request) as response:
        destination.write_bytes(
            response.read()
        )


def extract_aar(aar, destination):
    destination.mkdir(parents=True,exist_ok=True)

    with zipfile.ZipFile(aar, "r") as archive:
        names = archive.namelist()

        if "classes.jar" in names:
            archive.extract("classes.jar", destination)

        for name in names:
            if (
                name.startswith("libs/")
                and name.endswith(".jar")
            ):
                archive.extract(name, destination)


def strip_android_support(jar):
    tmp = jar.with_suffix(".tmp.jar")

    with zipfile.ZipFile(jar,"r") as src:
        with zipfile.ZipFile(
            tmp,
            "w",
            zipfile.ZIP_DEFLATED,
        ) as dst:

            for info in src.infolist():
                if info.filename.startswith("android/support/"):
                    continue

                dst.writestr(info,src.read(info.filename))

    tmp.replace(jar)


def collect_jars(artifact, work_dir):
    extension = artifact.suffix.lower()

    if extension == ".jar":
        jar = work_dir / artifact.name
        
        shutil.copy2(artifact,jar)

        strip_android_support(jar)

        with zipfile.ZipFile(jar, 'r') as zf:
            class_count = sum(1 for n in zf.namelist() if n.endswith('.class'))
            if class_count == 0:
                log(f"[WARN] {artifact.name}: 0 .class files found\n")

        return [jar]

    if extension == ".aar":
        aar_dir = work_dir / "aar"

        extract_aar(artifact,aar_dir)

        jars = []

        classes_jar = aar_dir / "classes.jar"
        
        if classes_jar.exists():
            strip_android_support(classes_jar)
            jars.append(classes_jar)

        for jar in sorted(
            (aar_dir / "libs").glob("*.jar")
            if (aar_dir / "libs").exists()
            else []
        ):
            strip_android_support(jar)
            jars.append(jar)

        return jars

    return []


def d8_to_dex(jars, output_dir):
    output_dir.mkdir(parents=True,exist_ok=True)

    command = [
        str(rosal.D8),
        "--release",
        "--min-api",
        "26",
        "--no-desugaring",
        "--lib",
        str(rosal.ANDROID_JAR),
        "--output",
        str(output_dir),
    ]

    command.extend(
        str(jar)
        for jar in jars
    )

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    
    if result.returncode != 0:
        raise RuntimeError(f"D8 failed: {result.stderr[:200] if result.stderr else 'unknown'}")
    
    generated = list(output_dir.glob("*.dex"))
    return generated


def remove_old_dex(stem, library_dex_dir):
    for path in library_dex_dir.glob(f"{stem}*.dex"):
        path.unlink()


def process_marker(parsed_marker, library_dex_dir):
    raw, version = parsed_marker

    resolved = resolve(raw)

    if resolved is None:
        log(f"[SKIPPING] {raw}:{version}\n(unknown mapping)\n\n------------------------------\n")
        return

    group, artifact = resolved
    repo = repo_for(group)

    stem = f"{raw}-{version}"

    log(f"[FETCHING] {raw}:{version}\n ---> {group}:{artifact}:{version}\n")

    with tempfile.TemporaryDirectory(prefix="rosal_fetch_") as tmp:
        tmp_dir = Path(tmp)
        artifact_dir = tmp_dir / "artifact"
        work_dir = tmp_dir / "work"
        d8_dir = tmp_dir / "d8"

        try:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            work_dir.mkdir(parents=True, exist_ok=True)

            # Try AAR first
            aar = artifact_dir / f"{artifact}.aar"
            aar_url = build_url(repo, group, artifact, version, "aar")

            try:
                download(aar_url, aar)
                artifact_file = aar

            except HTTPError:
                # Fallback to JAR
                jar = artifact_dir / f"{artifact}.jar"
                jar_url = build_url(repo, group, artifact, version, "jar")

                try:
                    download(jar_url, jar)
                    artifact_file = jar
                except HTTPError:
                    log(f"[NOCODE] {raw}:{version}\n\n------------------------------\n")
                    return

            jars = collect_jars(artifact_file, work_dir)

            if not jars:
                log(f"[NOCODE] {raw}:{version}\n\n------------------------------\n")
                return

            d8_to_dex(jars, d8_dir)

            generated = sorted(d8_dir.glob("*.dex"))

            if not generated:
                log(f"[EMPTY] {raw}:{version}\n\n------------------------------\n")
                return

            remove_old_dex(stem, library_dex_dir)

            for index, dex in enumerate(generated):
                if index == 0:
                    name = f"{stem}.dex"
                else:
                    name = f"{stem}-classes{index + 1}.dex"

                output = library_dex_dir / name
                shutil.copy2(dex, output)
                log(f"[OK] {output}\n\n------------------------------\n")

        except Exception as exc:
            log(f"[ERROR] {raw}:{version}:\n {exc}\n\n------------------------------\n")

def count_lines(file_path):
    with file_path.open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())

def main(markers_file=None, library_dex_dir=None):
    
    if markers_file is None:
        sys.exit(f"ERROR: {markers_file} not found")
    elif not markers_file.is_file():
        sys.exit(f"ERROR: {markers_file} is not a file")
    else:
        markers_file = Path(markers_file)

    if library_dex_dir is None:
        sys.exit(f"ERROR: {library_dex_dir} not found")
    else:
        library_dex_dir = Path(library_dex_dir)
        library_dex_dir.mkdir(parents=True, exist_ok=True)

    if not rosal.ANDROID_JAR.exists():
        sys.exit(
            f"ERROR: Android platform not found: "
            f"{rosal.ANDROID_JAR}"
        )

    if not rosal.D8.exists():
        sys.exit(f"ERROR: d8 not found: {rosal.D8}")

    already_processed = set()
    
    marker_count = count_lines(markers_file)

    with markers_file.open(encoding="utf-8") as markers:

        for line in tqdm(markers, total=marker_count, desc="Fetching library DEXs", colour="green"):
            parsed_marker = parse_marker(line)

            if parsed_marker is None or parsed_marker in already_processed:
                continue

            already_processed.add(parsed_marker)

            process_marker(parsed_marker, library_dex_dir)

    print(f"[+] Fetching library DEXs complete\n")


if __name__ == "__main__":
    main()
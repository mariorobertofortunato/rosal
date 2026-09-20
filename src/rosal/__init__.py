# __init__.py

import os
import re
from pathlib import Path


def _resolve_android_home() -> Path:
    env = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if env:
        return Path(env)
    return Path.home() / "Android" / "Sdk"

def _version_key(name: str) -> tuple[int, ...] | None:
    parts = re.findall(r"\d+", name)
    if not parts:
        return None
    return tuple(int(p) for p in parts)

def _latest_subdir(base: Path) -> Path:
    if not base.is_dir():
        raise FileNotFoundError(f"Directory not found: {base}")

    versioned = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        key = _version_key(d.name)
        if key is not None:
            versioned.append((key, d))

    if not versioned:
        raise FileNotFoundError(f"No subfolder in {base}")

    return max(versioned, key=lambda item: item[0])[1]


DEFAULT_WORK_DIR = Path.home() / "rosal"

# Android SDK paths
ANDROID_HOME = _resolve_android_home()
ANDROID_JAR = _latest_subdir(ANDROID_HOME / "platforms") / "android.jar"
D8 = _latest_subdir(ANDROID_HOME / "build-tools") / "d8"

# Maven repositories
GOOGLE_MAVEN = "https://dl.google.com/dl/android/maven2"
MAVEN_CENTRAL = "https://repo1.maven.org/maven2"


OVERRIDES = {
    "kotlinx_coroutines_core": ("org.jetbrains.kotlinx","kotlinx-coroutines-core-jvm", ),
    "kotlinx_coroutines_android": ("org.jetbrains.kotlinx","kotlinx-coroutines-android",),
    "kotlinx_coroutines_play_services": ("org.jetbrains.kotlinx","kotlinx-coroutines-play-services",),
}

VERSION_OVERRIDES = {
    "androidx.arch.core_core-runtime": ("androidx.arch.core","core-runtime",),
}

PLATFORM_PREFIXES = ("Landroid/", "Ljava/", "Ljavax/")
CONSTRUCTOR_NAMES = {"<init>", "<clinit>"}
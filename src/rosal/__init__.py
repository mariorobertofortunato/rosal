# __init__.py

from pathlib import Path

__version__ = "0.0.1"

DEFAULT_WORK_DIR = Path.home() / "rosal"

# Android SDK paths
ANDROID_HOME = Path.home() / "Android"/ "Sdk"
ANDROID_JAR = ANDROID_HOME / "platforms" / "android-34" / "android.jar"
D8 = ANDROID_HOME / "build-tools" / "37.0.0" / "d8"

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
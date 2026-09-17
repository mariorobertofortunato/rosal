 # ROSAL

ROSAL (Reverse Obfuscated Standard Android Libraries) helps reverse-engineer Android applications by mapping obfuscated classes from an APK to their plain-text equivalents in the declared standard libraries (androidx, core, ...).

It helps recover actual names for classes like RecyclerView, LiveData, Fragment, CompatActivity, and so on, partly automating the manual process of reverse engineering and allowing for an easier Static Analysis of Android apps.

The mapping is limited to the classes from the standard libraries: it does not involve the mapping of the proprietary classes of the app.

Fully deterministic, no heuristics.
No AI is involved in the process.

```text
!!!! DISCLAIMER !!!!
This software is intended for research and for testing on authorized targets EXCLUSIVELY.
Any other purpose is not supported or endorsed by the creators by any means.
Don't be a cunt.
```

## Getting started

### Prerequisites & Dependencies
Dependencies on `Androguard`, `loguru` and `tqdm` should be resolved automatically during installation... If not, install manually.

The tool relies on the Android SDK. You'll definitely need D8 and platform-tools. 

Install it in `~/Android/Sdk` ( <<-- please use this exact path, otherwise things will break)

```
https://developer.android.com/tools/releases/build-tools
https://developer.android.com/tools/releases/platform-tools
```

`Java` is also required. Install it if you haven't already.

### Installing from local repository

Clone the repository, then `cd` to its directory and:

```bash
python -m pip install .
```

Use the `-e` option if you wish to make it an editable installation

```bash
pip install -e .
```

### Installing from PyPi (recommended)

```bash
pip install rosal
```

## Run

```bash
# (Optional) Define APK path
export APK=...
```

Basic usage:

```bash
rosal --apk "$APK" # or <path_to_apk>
```

The command runs the fetch, extraction, catalog, matching and mapping stages in sequence.

By default, intermediate files and `matches.tiny` are written to `~/rosal`. 
Use `--work-dir` to specify another directory:

```bash
rosal --apk "$APK" --work-dir ./anything_you_want
```

### Relevant sample outputs

`matches.json`

```json
{
  "matches": [
    {
      "library_class": "Landroidx/activity/Api34Impl;",
      "target_class": "Landroidx/activity/a;",
      "provenance": "androidx.activity_activity-1.8.1.dex",
      "methods": [
        {
          "library_name": "createOnBackEvent",
          "target_name": "a",
          "library_descriptor": "(FFFI)Landroid/window/BackEvent;",
          "target_descriptor": "(FFFI)Landroid/window/BackEvent;"
        },
        {
          "library_name": "progress",
          "target_name": "b",
          "library_descriptor": "(Landroid/window/BackEvent;)F",
          "target_descriptor": "(Landroid/window/BackEvent;)F"
        },
        {
          "library_name": "swipeEdge",
          "target_name": "c",
          "library_descriptor": "(Landroid/window/BackEvent;)I",
          "target_descriptor": "(Landroid/window/BackEvent;)I"
        },
        {
          "library_name": "touchX",
          "target_name": "d",
          "library_descriptor": "(Landroid/window/BackEvent;)F",
          "target_descriptor": "(Landroid/window/BackEvent;)F"
        },
        {
          "library_name": "touchY",
          "target_name": "e",
          "library_descriptor": "(Landroid/window/BackEvent;)F",
          "target_descriptor": "(Landroid/window/BackEvent;)F"
        }
      ],
      "fields": []
    },
    ...
```
`matches.tiny`

```text
tiny	2	0	obf	named
c	androidx/activity/a	androidx/activity/Api34Impl
	m	(FFFI)Landroid/window/BackEvent;	a	createOnBackEvent
	m	(Landroid/window/BackEvent;)F	b	progress
	m	(Landroid/window/BackEvent;)I	c	swipeEdge
	m	(Landroid/window/BackEvent;)F	d	touchX
	m	(Landroid/window/BackEvent;)F	e	touchY
c	androidx/activity/p	androidx/activity/ComponentActivity
c	androidx/activity/q	androidx/activity/ComponentDialog
c	androidx/activity/s	androidx/activity/OnBackPressedCallback
c	androidx/activity/w	androidx/activity/OnBackPressedDispatcher$Api33Impl
```

### Files and Directories involved

With the exception of `matches.tiny`, these files are intermediates that can end up being quite large.
Feel free to delete them if you don't need them for further analysis.

```text
markers_file = work_dir / "markers.txt"
library_dex_dir = work_dir / "library_dex"
target_dex_dir = work_dir / "target_dex"
features_file = work_dir / "features.ndjson"
catalog_file = work_dir / "catalog.json"
matches_file = work_dir / "matches.json"
mapping_file = work_dir / "matches.tiny"
```

### Applying the `matches.tiny` file

Once the command has (hopefully) run successfully, you can apply the generated `matches.tiny` to an instance of `jadx` / `jadx-gui`

```bash
jadx-gui --mappings-path <path_to>/matches.tiny "$APK"
```

## License

This project is licensed under the MIT License - see the LICENSE.md file for details

## Acknowledgments

* Android SDK
* [Androguard](https://github.com/androguard/androguard) Team, and their fantastic job
* [tqdm](https://github.com/tqdm/tqdm)
* Inspiration: [LibScan](https://github.com/wyf295/LibScan), [deoptfuscator](https://github.com/Gyoonus/deoptfuscator), [DexKit](https://github.com/LuckyPray/DexKit), [KMparse](https://github.com/mforlini/KMparse)
 # ROSAL

ROSAL (Reverse Obfuscated Standard Android Libraries) helps in the process of reverse-engineering Android Applications, mapping obfuscated classes from an APK with their plain text correspondence in the standard libraries (androidx,core,...)
It helps recover actual names for classes like RecyclerView, LiveData, Fragment, CompatActivity, and so on, partly automating the manual process of reverse engineering and allowing for an easier Static Analysis of Android apps.
The mapping is limited to the calsses from the standard libraries: it does not involve the mapping of the proprietary calsses of the app.

Fully deterministic, no euristic.
No AI is involved in the process.

## Install

```bash
python -m pip install .
```

## Run

Basic usage:

```bash
rosal --apk <path_to_apk>
```

The command runs the fetch, extraction, catalog, matching and mapping stages in sequence.


If you want to specify the work directory:

```bash
rosal --apk <path_to_apk> --work-dir ./anything_you_want
```

By default, intermediate files and `matches.tiny` are written to `~/rosal`. 
Use `--work-dir` to choose another directory.


## Preliminary

```bash
# (Optional) Define APK path
export APK=...
```


## Files and Directories

markers_file = work_dir / "markers.txt"
library_dex_dir = work_dir / "library_dex"
target_dex_dir = work_dir / "target_dex"
features_file = work_dir / "features.ndjson"
catalog_file = work_dir / "catalog.json"
matches_file = work_dir / "matches.json"
mapping_file = work_dir / "matches.tiny"
#!/usr/bin/env python3

# DEPRECATED: This module is deprecated and will be removed in future versions.

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x


def add_to_index(index, value, class_key):
    index.setdefault(value, []).append(class_key)


def count_features(file_path):
    with file_path.open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def main(features_file=None, catalog_file=None):

    if features_file is None or catalog_file is None:
        sys.exit("ERROR: features_file and catalog_file must be specified")

    features_file = Path(features_file)
    catalog_file = Path(catalog_file)

    if not features_file.exists():
        sys.exit(f"ERROR: {features_file} not found")

    classes = []
    artifacts = Counter()
    fp_index = defaultdict(list)
    string_index = defaultdict(list)
    number_index = defaultdict(list)
    invoke_index = defaultdict(list)
    class_ref_index = defaultdict(list)

    features_count = count_features(features_file)

    for line in tqdm(features_file.open(encoding="utf-8"), total=features_count, desc="Parsing features --> catalog", colour="green"):
        line = line.strip()

        if not line:
            continue

        entry = json.loads(line)

        classes.append(entry)
        class_name = entry["class_name"]
        provenance = entry["provenance"]
        artifacts[provenance] += 1
        class_key = (f"{class_name}@@{provenance}")

        for method in entry.get("methods",[]):
            fp = method.get("fp")

            if fp:
                add_to_index(fp_index, fp, class_key)

            for method_string in method.get("method_strings",[]):
                add_to_index(string_index, method_string, class_key)

            for method_number in method.get("method_numbers", []):
                add_to_index(number_index, method_number, class_key)

            for method_invoke in method.get("method_invokes", []):
                add_to_index(invoke_index, method_invoke, class_key)

        for class_ref in entry.get("class_refs",[]):
            add_to_index(class_ref_index, class_ref, class_key)

        for entry_string in entry.get("strings", []):
            add_to_index(string_index, entry_string, class_key)

        for entry_number in entry.get("numbers", []):
            add_to_index(number_index, entry_number, class_key,)

        for entry_invoke in entry.get("invokes", []):
            add_to_index(invoke_index, entry_invoke, class_key)

    catalog = {
        "classes": classes,
        "indexes": {
            "fp": dict(fp_index),
            "strings": dict(string_index),
            "numbers": dict(number_index),
            "invokes": dict(invoke_index),
            "class_refs": dict(class_ref_index),
        },
        "stats": {
            "classes": len(classes),
            "artifacts": len(artifacts),
            "classes_per_artifact": dict(artifacts),
            "fp_distinct": len(fp_index),
            "strings_distinct": len(string_index),
            "numbers_distinct": len(number_index),
            "invokes_distinct": len(invoke_index),
            "class_refs_distinct": len(class_ref_index),
        },
    }

    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    with catalog_file.open(mode="w", encoding="utf-8") as out:
        json.dump(catalog, out, indent=2, sort_keys=False)

    print(f"[+] classes               : {len(classes)}")
    print(f"[+] artifacts             : {len(artifacts)}")
    print(f"[+] fp distinct           : {len(fp_index)}")
    print(f"[+] strings distinct      : {len(string_index)}")
    print(f"[+] numbers distinct      : {len(number_index)}")
    print(f"[+] invokes distinct      : {len(invoke_index)}")
    print(f"[+] class_refs distinct   : {len(class_ref_index)}")
    print(f"[+] output                : {catalog_file}\n")


if __name__ == "__main__":
    main()
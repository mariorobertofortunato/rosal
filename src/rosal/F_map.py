#!/usr/bin/env python3

import json
import sys
from pathlib import Path


def clean_name(name):
    if name.startswith("L") and name.endswith(";"):
        name = name[1:-1]
    return name.replace(".", "/")

def valid_descriptor(desc):
    return bool(desc) and "?" not in desc

def main(matches_file=None, mapping_file=None):

    if matches_file is None or mapping_file is None:
        sys.exit("ERROR: matches_file and mapping_file must be specified")

    matches_file = Path(matches_file)
    mapping_file = Path(mapping_file)

    with matches_file.open(encoding="utf-8") as f:
        data = json.load(f)

    matches = data.get("matches", [])

    if not matches:
        print(f"WARNING: No matches found in {matches_file}")
        return

    seen = set()
    skipped = 0
    total_methods = 0

    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    with mapping_file.open(mode="w", encoding="utf-8") as out:

        out.write("tiny\t2\t0\tobf\tnamed\n")

        for match in matches:
            real = clean_name(match["library_class"])  
            obf = clean_name(match["target_class"])     

            pair = (real, obf)

            if pair in seen:
                continue

            seen.add(pair)

            out.write(f"c\t{obf}\t{real}\n")

            for method in match.get("methods", []):
                total_methods += 1
                desc = method.get("target_descriptor", "")
                tgt_name = method.get("target_name", "")
                lib_name = method.get("library_name", "")

                if not valid_descriptor(desc):
                    skipped += 1
                    continue

                out.write(f"\tm\t{desc}\t{tgt_name}\t{lib_name}\n")

            for field in match.get("fields", []):
                desc = field.get("target_descriptor", "")
                tgt_name = field.get("target_name", "")
                lib_name = field.get("library_name", "")

                if not valid_descriptor(desc):
                    skipped += 1
                    continue

                out.write(f"\tf\t{desc}\t{tgt_name}\t{lib_name}\n")

    print(f"accepted : {len(seen)}")
    print(f"methods  : {total_methods - skipped}/{total_methods} (skipped: {skipped})")
    print(f"output   : {mapping_file.absolute()}")


if __name__ == "__main__":
    main()
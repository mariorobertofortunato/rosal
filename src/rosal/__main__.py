"""Command-line entry point"""

import argparse
import rosal
from pathlib import Path

from rosal import A_prep, B_fetch, D_match, E_map

def build_parser():
    parser = argparse.ArgumentParser(
        prog="rosal",
        #description="Fetch, catalog, match and map Android library classes.",
    )
    # Optionallly define the work directory
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=rosal.DEFAULT_WORK_DIR,
        help="Directory for intermediate and output files (default: ~/rosal)",
    )
    parser.add_argument(
        "--apk",
        type=Path,
        help="APK to analyze.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    work_dir = args.work_dir.expanduser().resolve()
    markers_file = work_dir / "markers.txt"
    target_dex_dir = work_dir / "target_dex"
    library_dex_dir = work_dir / "library_dex"
    matches_file = work_dir / "matches.json"
    mapping_file = work_dir / "matches.tiny"

    if args.apk is not None:
        A_prep.main(args.apk, markers_file, target_dex_dir)
    else:
        parser.error("provide --apk")

    B_fetch.main(markers_file, library_dex_dir)
    D_match.main(library_dex_dir, target_dex_dir, matches_file)
    E_map.main(matches_file, mapping_file)

    print(f"[+] mapping: {mapping_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
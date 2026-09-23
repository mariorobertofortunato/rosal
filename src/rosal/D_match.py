#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from collections import defaultdict
from rosal.models import ClassInfo

from .C_extract import extract_from_dex

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x


# --------------------------------------------------------------------------- #
# Indexes
# --------------------------------------------------------------------------- #

def build_method_index(classes: list[ClassInfo]):
    """anchor_key -> [(ClassInfo, MethodInfo), ...]"""
    index = defaultdict(list)
    for cls in classes:
        for method in cls.methods:
            if method.is_concrete() and method.has_anchor_evidence():
                index[method.anchor_key()].append((cls, method))
    return index


def build_field_index(classes: list[ClassInfo]):
    """anchor_key -> [(ClassInfo, FieldInfo), ...]"""
    index = defaultdict(list)
    for cls in classes:
        for field in cls.fields:
            if field.has_anchor_evidence():
                index[field.anchor_key()].append((cls, field))
    return index


def build_class_index(classes: list[ClassInfo]):
    """(package, platform_superclass) -> [ClassInfo, ...]"""
    index = defaultdict(list)
    for cls in classes:
        index[cls.lookup_key()].append(cls)
    return index


# --------------------------------------------------------------------------- #
# Verify
# --------------------------------------------------------------------------- #

def class_compatible(target_cls: ClassInfo, library_cls: ClassInfo) -> bool:
    if not target_cls.class_name or not library_cls.class_name:
        return False
    if target_cls.class_name == library_cls.class_name:
        return False
    if target_cls.package != library_cls.package:
        return False

    if (
        target_cls.platform_superclass
        and library_cls.platform_superclass
        and target_cls.platform_superclass != library_cls.platform_superclass
    ):
        return False

    if not target_cls.platform_interfaces.issubset(library_cls.platform_interfaces):
        return False

    if len(target_cls.methods) > len(library_cls.methods):
        return False
    if len(target_cls.fields) > len(library_cls.fields):
        return False

    return True


def find_anchors(target_cls: ClassInfo, library_cls: ClassInfo, library_method_index, library_field_index):

    def resolve(target_item, index):
        locations = index.get(target_item.anchor_key(), [])
        in_class = [item for owner, item in locations if owner is library_cls]
        if len(in_class) != 1:
            return None
        return in_class[0]

    method_anchors = []
    for method in target_cls.methods:
        if not (method.is_concrete() and method.has_anchor_evidence()):
            continue
        match = resolve(method, library_method_index)
        if match is not None:
            method_anchors.append((method, match))

    field_anchors = []
    for field in target_cls.fields:
        if not field.has_anchor_evidence():
            continue
        match = resolve(field, library_field_index)
        if match is not None:
            field_anchors.append((field, match))

    return method_anchors, field_anchors


def anchors_are_distinct(anchors) -> bool:
    libs = [l for _, l in anchors]
    return len(set(libs)) == len(libs)


def build_mapping(target_item, library_item, label) -> dict:
    return {
        f"library_{label}_name": library_item.name,
        f"target_{label}_name": target_item.name,
        f"library_{label}_descriptor": library_item.descriptor,
        f"library_{label}_descriptor_raw": library_item.descriptor_raw,
        f"target_{label}_descriptor": target_item.descriptor,
        f"target_{label}_descriptor_raw": target_item.descriptor_raw,
    }


def verify_class(target_cls: ClassInfo, library_cls: ClassInfo, library_method_index, library_field_index):
    if not class_compatible(target_cls, library_cls):
        return None

    method_anchors, field_anchors = find_anchors(
        target_cls, library_cls, library_method_index, library_field_index
    )

    if not anchors_are_distinct(method_anchors):
        return None
    if not anchors_are_distinct(field_anchors):
        return None

    method_mappings = [
        build_mapping(target_method, library_method, "method") for target_method, library_method in method_anchors if target_method.name != library_method.name
    ]
    field_mappings = [
        build_mapping(target_field, library_field, "field") for target_field, library_field in field_anchors if target_field.name != library_field.name
    ]

    if not method_mappings and not field_mappings and not method_anchors and not field_anchors:
        return None

    return {
        "methods": method_mappings,
        "fields": field_mappings,
        "anchor_count": len(method_anchors) + len(field_anchors),
    }


# --------------------------------------------------------------------------- #
# I/O e main
# --------------------------------------------------------------------------- #


def match_classes(
    target_classes: list[ClassInfo],
    library_classes: list[ClassInfo],
) -> list[dict]:

    t_names = {c.class_name for c in target_classes}
    l_names = {c.class_name for c in library_classes}
    overlap = t_names & l_names

    target_classes = [c for c in target_classes if c.class_name not in overlap]
    library_classes = [c for c in library_classes  if c.class_name not in overlap]


    library_method_index = build_method_index(library_classes)
    library_field_index  = build_field_index(library_classes)
    library_class_index  = build_class_index(library_classes)

    candidates: dict[int, dict[int, tuple[ClassInfo, ClassInfo, dict]]] = {}

    for target_cls in tqdm(target_classes, total=len(target_classes), desc="Matching classes", colour="green"):
        for library_cls in library_class_index.get(target_cls.lookup_key(), []):
            verified = verify_class(
                target_cls, library_cls, library_method_index, library_field_index
            )
            if verified is None:
                continue
            candidates.setdefault(id(target_cls), {})[id(library_cls)] = (
                target_cls, library_cls, verified,
            )

    contenders: dict[int, set[int]] = defaultdict(set)

    for t_id, libs in candidates.items():
        for l_id in libs:
            contenders[l_id].add(t_id)


    matches: list[dict] = []

    for t_id, libs in candidates.items():
        if len(libs) != 1:
            continue
        l_id = next(iter(libs))
        if len(contenders[l_id]) != 1:
            continue

        target_cls, library_cls, verified = libs[l_id]
        matches.append({
            "library_class": library_cls.class_name,
            "target_class":  target_cls.class_name,
            "provenance":    library_cls.provenance,
            "methods":       verified["methods"],
            "fields":        verified["fields"],
        })

    return matches


def main(library_dex_dir=None, target_dex_dir=None, matches_file=None):

    if library_dex_dir is None or target_dex_dir is None or matches_file is None:
        sys.exit("ERROR: library_dex_dir, target_dex_dir and matches_file must be specified")

    library_dex_paths = list(library_dex_dir.glob("*.dex"))
    target_dex_paths = list(target_dex_dir.glob("*.dex"))
    matches_file = Path(matches_file)


    # Target classes
    target_classes = extract_from_dex(target_dex_paths, label="target")

    # Library classes
    library_classes = extract_from_dex(library_dex_paths, label="library")

    matches = match_classes(target_classes, library_classes)

    output = {
        "matches": matches,
        "stats": {
            "library_classes": len(library_classes),
            "target_classes": len(target_classes),
            "matches": len(matches),
        },
    }

    matches_file.parent.mkdir(parents=True, exist_ok=True)
    matches_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[+] library classes : {len(library_classes)}")
    print(f"[+] target classes  : {len(target_classes)}")
    print(f"[+] matches         : {len(matches)}")
    print(f"[+] output          : {matches_file}\n")


if __name__ == "__main__":
    main()
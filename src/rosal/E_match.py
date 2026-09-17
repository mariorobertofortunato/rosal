#!/usr/bin/env python3

import json
import sys
import rosal
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .C_extract import extract_dex_features

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x


# --------------------------------------------------------------------------- #
# Descriptor helpers
# --------------------------------------------------------------------------- #

def class_package(class_name: str) -> str:
    if not isinstance(class_name, str):
        return ""
    pos = class_name.rfind("/")
    return class_name if pos == -1 else class_name[:pos]


def is_platform_ref(value) -> bool:
    return isinstance(value, str) and value.startswith(rosal.PLATFORM_PREFIXES)


def normalize_descriptor(desc: str) -> str:
    """Substitutes app's internal types with 'L?;', leaving intact
    primitives, arrays and references to platform classes."""
    if not isinstance(desc, str):
        return ""

    out = []
    i = 0
    while i < len(desc):
        c = desc[i]

        if c == "[" or c in "VZBSCIJFD":
            out.append(c)
            i += 1
            continue

        if c == "L":
            end = desc.find(";", i)
            if end == -1:
                return desc
            ref = desc[i:end + 1]
            out.append(ref if is_platform_ref(ref) else "L?;")
            i = end + 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


def descriptor_is_level_a(normalized_desc: str) -> bool:
    return "L?;" not in normalized_desc


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class MethodInfo:
    name: str
    descriptor: str         
    access: int
    has_body: bool
    strings: frozenset[str]
    api_refs: frozenset[str]
    class_refs: frozenset[str]
    invokes: frozenset[str]
    annotation_types: frozenset[str]

    def is_concrete(self) -> bool:
        return self.name not in rosal.CONSTRUCTOR_NAMES and self.has_body

    def has_anchor_evidence(self) -> bool:
        return bool(
            self.strings or self.api_refs or self.class_refs
            or self.invokes or self.annotation_types
        )

    def anchor_key(self):
        return (
            self.descriptor,
            self.access,
            tuple(sorted(self.strings)),
            tuple(sorted(self.api_refs)),
            tuple(sorted(self.class_refs)),
            tuple(sorted(self.invokes)),
            tuple(sorted(self.annotation_types)),
        )


@dataclass(frozen=True)
class FieldInfo:
    name: str
    descriptor: str         
    access: int

    def has_anchor_evidence(self) -> bool:
        return descriptor_is_level_a(self.descriptor)

    def anchor_key(self):
        return (self.descriptor, self.access)


@dataclass
class ClassInfo:
    class_name: str
    package: str
    superclass: str | None
    interfaces: frozenset
    methods: list[MethodInfo]
    fields: list[FieldInfo]
    provenance: str | None = None

    @property
    def platform_superclass(self):
        return self.superclass if is_platform_ref(self.superclass) else None

    @property
    def platform_interfaces(self):
        return frozenset(x for x in self.interfaces if is_platform_ref(x))

    def lookup_key(self):
        """(package, superclass)"""
        return (self.package, self.platform_superclass)


# --------------------------------------------------------------------------- #
# Model builders
# --------------------------------------------------------------------------- #

def make_method(raw: dict) -> MethodInfo:
    return MethodInfo(
        name=raw.get("method_name", ""),
        descriptor=normalize_descriptor(raw.get("method_descriptor", "")),
        access=raw.get("method_access", 0),
        has_body=bool(raw.get("opcodes")),
        strings=frozenset(raw.get("method_strings", [])),
        api_refs=frozenset(x for x in raw.get("method_api_refs", []) if is_platform_ref(x)),
        class_refs=frozenset(x for x in raw.get("method_class_refs", []) if is_platform_ref(x)),
        invokes=frozenset(x for x in raw.get("method_invokes", []) if is_platform_ref(x)),
        annotation_types=frozenset(
            x for x in raw.get("annotation_types", []) if is_platform_ref(x)
        ),
    )


def make_field(raw: dict) -> FieldInfo:
    return FieldInfo(
        name=raw.get("field_name", ""),
        descriptor=normalize_descriptor(raw.get("field_descriptor", "")),
        access=raw.get("field_access", 0),
    )


def make_class(entry: dict) -> ClassInfo:
    class_name = entry.get("class_name", "")
    return ClassInfo(
        class_name=class_name,
        package=class_package(class_name),
        superclass=entry.get("superclass"),
        interfaces=frozenset(
            x for x in entry.get("interfaces", []) if isinstance(x, str)
        ),
        methods=[make_method(m) for m in entry.get("methods", [])],
        fields=[make_field(f) for f in entry.get("fields", [])],
        provenance=entry.get("provenance"),
    )


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


def find_anchors(target_cls: ClassInfo, library_cls: ClassInfo, method_index, field_index):

    def resolve(tar_item, index):
        locations = index.get(tar_item.anchor_key(), [])
        in_class = [item for owner, item in locations if owner is library_cls]
        if len(in_class) != 1:
            return None
        return in_class[0]

    method_anchors = []
    for method in target_cls.methods:
        if not (method.is_concrete() and method.has_anchor_evidence()):
            continue
        match = resolve(method, method_index)
        if match is not None:
            method_anchors.append((method, match))

    field_anchors = []
    for field in target_cls.fields:
        if not field.has_anchor_evidence():
            continue
        match = resolve(field, field_index)
        if match is not None:
            field_anchors.append((field, match))

    return method_anchors, field_anchors


def anchors_are_distinct(anchors) -> bool:
    libs = [l for _, l in anchors]
    return len(set(libs)) == len(libs)


def build_mapping(target_item, library_item) -> dict:
    return {
        "library_name": library_item.name,
        "target_name": target_item.name,
        "library_descriptor": library_item.descriptor,
        "target_descriptor": target_item.descriptor,
    }


def verify_class(target_cls: ClassInfo, library_cls: ClassInfo, method_index, field_index):
    if not class_compatible(target_cls, library_cls):
        return None

    method_anchors, field_anchors = find_anchors(
        target_cls, library_cls, method_index, field_index
    )

    if not anchors_are_distinct(method_anchors):
        return None
    if not anchors_are_distinct(field_anchors):
        return None

    method_mappings = [
        build_mapping(tar_m, lib_m) for tar_m, lib_m in method_anchors if tar_m.name != lib_m.name
    ]
    field_mappings = [
        build_mapping(tar_field, lib_field) for tar_field, lib_field in field_anchors if tar_field.name != lib_field.name
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

def load_json(path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def extract_all_library_dex(paths):
    classes = []
    for p in paths:
        p = Path(p)
        if not p.is_file():
            sys.exit(f"ERROR: DEX not found: {p}")
        classes.extend(extract_dex_features(p, p.name))
    return classes


def match_classes(
    target_classes: list[ClassInfo],
    library_classes: list[ClassInfo],
) -> list[dict]:

    t_names = {c.class_name for c in target_classes}
    l_names = {c.class_name for c in library_classes}
    overlap = t_names & l_names

    target_classes = [c for c in target_classes if c.class_name not in overlap]
    library_classes = [c for c in library_classes  if c.class_name not in overlap]


    method_index = build_method_index(library_classes)
    field_index  = build_field_index(library_classes)
    class_index  = build_class_index(library_classes)

    candidates: dict[int, dict[int, tuple[ClassInfo, ClassInfo, dict]]] = {}

    #for target_cls in target_classes:
    for target_cls in tqdm(target_classes, total=len(target_classes), desc="Progress", colour="green"):
        for library_cls in class_index.get(target_cls.lookup_key(), []):
            verified = verify_class(
                target_cls, library_cls, method_index, field_index
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


def main(library_dex_dir=None, catalog_file=None, matches_file=None):

    if library_dex_dir is None or catalog_file is None or matches_file is None:
        sys.exit("ERROR: library_dex_dir, catalog_file and matches_file must be specified")

    if not catalog_file.is_file():
        sys.exit(f"ERROR: catalog not found: {catalog_file}")

    catalog_file = Path(catalog_file)
    matches_file = Path(matches_file)


    # Target classes
    catalog = load_json(catalog_file)
    target_classes = [make_class(entry) for entry in catalog.get("classes", [])]

    # Library classes
    library_classes = [
        make_class(entry) for entry in extract_all_library_dex(library_dex_dir)
    ]
    
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

    print(f"library classes : {len(library_classes)}")
    print(f"target classes  : {len(target_classes)}")
    print(f"matches         : {len(matches)}")
    print(f"output          : {matches_file}")


if __name__ == "__main__":
    main()
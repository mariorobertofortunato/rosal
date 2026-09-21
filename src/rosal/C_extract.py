#!/usr/bin/env python3

import hashlib
import json
import re
import sys
from pathlib import Path
from androguard.core.dex import DEX

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x

try:
    from loguru import logger
    logger.remove() 
except ImportError:
    pass


CLASS_DESCRIPTOR_RE = re.compile(r"L[^;]+;")


def strip_string_literal(value):
    if (
        isinstance(value, str)
        and len(value) >= 2
        and value[0] == "'"
        and value[-1] == "'"
    ):
        return value[1:-1]

    return value

def normalize_descriptor(descriptor):
    if not isinstance(descriptor, str):
        return descriptor
    return descriptor.replace(" ", "")


def extract_class_descriptors(value):
    if not isinstance(value, str):
        return set()

    value = normalize_descriptor(value)
    return set(CLASS_DESCRIPTOR_RE.findall(value))


def extract_method(method):
    code = method.get_code()

    n_insns = 0
    strings = set()
    numbers = set()
    api_refs = set()
    invokes = set()
    class_refs = set()
    opcodes = []
    descriptor = normalize_descriptor(method.get_descriptor())

    class_refs.update(
        extract_class_descriptors(descriptor)
    )

    if code is not None:

        for ins in code.get_bc().get_instructions():
            n_insns += 1

            name = ins.get_name()

            opcodes.append(name)

            try:
                operands = ins.get_operands(0)
            except Exception:
                operands = []

            if not operands:
                continue

            for operand in operands:
                if not isinstance(operand, tuple):
                    continue

                if not operand:
                    continue

                value = operand[-1]

                class_refs.update(extract_class_descriptors(value))

                if (name.startswith("const-string") and isinstance(value, str)):
                    strings.add(strip_string_literal(value))

                if (name.startswith("const") and isinstance(value,(int, float))):
                    numbers.add(value)

                if (name.startswith("invoke") and isinstance(value, str)):
                    value = normalize_descriptor(value)

                    invokes.add(value)

                    if value.startswith(("Landroid/", "Ljava/", "Ljavax/")):
                        api_refs.add(value)

    return {
        "method_name": method.get_name(),
        "method_descriptor": descriptor,
        "method_access": method.get_access_flags(),
        "n_insns": n_insns,
        "opcodes": opcodes,
        "method_strings": sorted(strings),
        "method_numbers": sorted(numbers),
        "method_api_refs": sorted(api_refs),
        "method_invokes": sorted(invokes),
        "method_class_refs": sorted(class_refs),
    }


def extract_field(field):
    return {
        "field_name": field.get_name(),
        "field_descriptor": normalize_descriptor(field.get_descriptor()),
        "field_access": field.get_access_flags(),
    }

# Keep in mind that this method is also used for extracting features 
# from library dex (so name variables accordingly = generalizing, is ok. 
# Basically DONT TOUCH THIS UNLESS EXTREMELY NECESSARY)
def extract_dex_features(dex_path, provenance, label):
    data = dex_path.read_bytes()

    dex = DEX(data)
    classes = dex.get_classes()

    for cls in tqdm(classes, total=len(classes), desc=f"Extracting {label} features ({dex_path.name})", colour="green"):
        class_name = cls.get_name()
        fields = []
        methods = []

        # fields
        for field in cls.get_fields():
            extracted_field = extract_field(field)

            fields.append(extracted_field)

        # methods
        for method in cls.get_methods():
            extracted_method = extract_method(method)

            methods.append(extracted_method)

        # interfaces
        try:
            interfaces = cls.get_interfaces()
        except Exception:
            interfaces = []

        interfaces = sorted([normalize_descriptor(i) for i in interfaces if i])

        # superclass
        try:
            superclass = normalize_descriptor(cls.get_superclassname())
        except Exception:
            superclass = None

        yield {
            "class_name": class_name,
            "superclass": superclass,
            "interfaces": interfaces,
            "provenance": provenance,
            "fields": fields,
            "methods": methods,
        }


def main(target_dex_dir=None, features_file=None):

    if target_dex_dir is None or features_file is None:
        sys.exit("ERROR: target_dex_dir and features_file must be provided")
    
    target_dex_dir = Path(target_dex_dir)
    features_file = Path(features_file)
    dex_files = sorted(target_dex_dir.glob("*.dex"))

    if not dex_files:
        sys.exit(f"No DEX files found in {target_dex_dir}")

    features_file.parent.mkdir(parents=True, exist_ok=True)

    with features_file.open(mode="w", encoding="utf-8") as output_handle:

        for dex_path in dex_files:
            provenance = dex_path.stem

            for feature in extract_dex_features(dex_path,provenance, label="target"):
                output_handle.write(
                    json.dumps(
                        feature,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )

    print(f"[+] Extracting target features complete")
    print(f"[+] output: {features_file}\n")


if __name__ == "__main__":
    main()
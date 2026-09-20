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


def normalize_annotation_value(value):
    try:
        obj = value.get_obj()
    except Exception:
        return repr(value)

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (list, tuple)):
        return [
            normalize_annotation_value(x)
            for x in obj
        ]

    return repr(obj)


def extract_annotations(cls):
    result = []

    try:
        annotation_data = cls.get_annotations()

        if annotation_data is None:
            return result

        if hasattr(annotation_data, "get_annotations"):
            annotations = annotation_data.get_annotations()

        elif hasattr(annotation_data, "get_annotation_off_item"):
            annotations = []

            for off_item in (annotation_data.get_annotation_off_item()):
                try:
                    annotation = (off_item.get_annotation_item())

                    if annotation is not None:
                        annotations.append(annotation)

                except Exception:
                    continue

        elif isinstance(annotation_data, (list, tuple)):
            annotations = annotation_data

        else:
            return result

        for annotation in annotations:
            try:
                encoded = (
                    annotation.get_annotation()
                    if hasattr(annotation, "get_annotation")
                    else annotation
                )

                if not hasattr(encoded, "get_type"):
                    continue

                annotation_type = encoded.get_type()

                elements = {}

                if hasattr(encoded, "get_elements"):
                    for element in encoded.get_elements():
                        try:
                            name = (element.get_name())
                            value = (normalize_annotation_value(element.get_value()))
                            elements[name] = value

                        except Exception:
                            continue

                result.append({
                    "type": annotation_type,
                    "elements": elements,
                })

            except Exception:
                continue

    except Exception:
        return result

    return result


def extract_method(method):
    code = method.get_code()

    n_insns = 0
    fp = None
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
        mnemonics = []

        for ins in code.get_bc().get_instructions():
            n_insns += 1

            name = ins.get_name()

            mnemonics.append(name)
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

                if (
                    name.startswith("const-string")
                    and isinstance(value, str)
                ):
                    strings.add(strip_string_literal(value))

                if (
                    name.startswith("const")
                    and isinstance(value,(int, float))
                ):
                    numbers.add(value)

                if (
                    name.startswith("invoke")
                    and isinstance(value, str)
                ):
                    value = normalize_descriptor(value)

                    invokes.add(value)

                    if value.startswith((
                        "Landroid/",
                        "Ljava/",
                        "Ljavax/",
                    )):
                        api_refs.add(value)

        fp_input = ("|".join(mnemonics) + "|" + descriptor)

        fp = hashlib.sha256(fp_input.encode("utf-8")).hexdigest()

    return {
        "method_name": method.get_name(),
        "method_descriptor": descriptor,
        "method_access": method.get_access_flags(),
        "fp": fp,
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
        class_strings = set()
        class_numbers = set()
        class_api_refs = set()
        class_invokes = set()
        class_refs = set()

        # fields
        for field in cls.get_fields():
            extracted_field = extract_field(field)

            fields.append(extracted_field)

            class_refs.update(
                extract_class_descriptors(extracted_field["field_descriptor"])
            )

        # methods (and strings, numbers, api_refs, invokes, class_refs)
        for method in cls.get_methods():
            extracted_method = extract_method(method)

            methods.append(extracted_method)

            class_strings.update(extracted_method["method_strings"])

            class_numbers.update(extracted_method["method_numbers"])

            class_api_refs.update(extracted_method["method_api_refs"])

            class_invokes.update(extracted_method["method_invokes"])

            class_refs.update(extracted_method["method_class_refs"])

        # annotations
        extracted_annotations = extract_annotations(cls)

        annotation_types = sorted(
            annotation["type"]
            for annotation in extracted_annotations
        )

        for annotation_type in annotation_types:
            class_refs.update(
                extract_class_descriptors(annotation_type)
            )

        # interfaces
        try:
            interfaces = cls.get_interfaces()
        except Exception:
            interfaces = []

        for interface in interfaces:
            class_refs.update(
                extract_class_descriptors(interface)
            )

        interfaces = sorted([normalize_descriptor(i) for i in interfaces if i])

        # superclass
        try:
            superclass = normalize_descriptor(cls.get_superclassname())
        except Exception:
            superclass = None

        class_refs.update(
            extract_class_descriptors(superclass)
        )

        # class access
        try:
            class_access = cls.get_access_flags()
        except Exception:
            class_access = 0

        class_refs.discard(class_name)

        yield {
            "class_name": class_name,
            "superclass": superclass,
            "interfaces": interfaces,
            "access": class_access,
            "provenance": provenance,
            "fields": fields,
            "methods": methods,
            "annotations": extracted_annotations,
            "annotation_types": annotation_types,
            "strings": sorted(class_strings),
            "numbers": sorted(class_numbers),
            "api_refs": sorted(class_api_refs),
            "invokes": sorted(class_invokes),
            "class_refs": sorted(class_refs),
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
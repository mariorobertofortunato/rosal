#!/usr/bin/env python3

import re
import sys
from pathlib import Path
from androguard.core.dex import DEX

from rosal.models import ClassInfo, MethodInfo, FieldInfo
from rosal.utils import is_platform_ref, normalize_descriptor

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

def strip_descriptor_spaces(descriptor):
    if not isinstance(descriptor, str):
        return descriptor
    return descriptor.replace(" ", "")


def extract_class_descriptors(value):
    if not isinstance(value, str):
        return set()

    value = strip_descriptor_spaces(value)
    return set(CLASS_DESCRIPTOR_RE.findall(value))


def extract_method(method) -> MethodInfo:
    code = method.get_code()

    n_insns = 0
    strings = set()
    numbers = set()
    api_refs = set()
    invokes = set()
    class_refs = set()
    opcodes = []
    descriptor_raw = strip_descriptor_spaces(method.get_descriptor())

    class_refs.update(
        extract_class_descriptors(descriptor_raw)
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
                    value = strip_descriptor_spaces(value)

                    invokes.add(value)

                    if is_platform_ref(value):
                        api_refs.add(value)

    return MethodInfo(
        name=method.get_name(),
        descriptor=normalize_descriptor(descriptor_raw),
        descriptor_raw=descriptor_raw,
        access=method.get_access_flags(),
        n_insns=n_insns,
        has_body=n_insns > 0,
        strings=frozenset(strings),
        numbers=frozenset(numbers),
        api_refs=frozenset(api_refs),
        class_refs=frozenset(x for x in class_refs if is_platform_ref(x)),
        invokes=frozenset(x for x in invokes if is_platform_ref(x)),
    )


def extract_field(field) -> FieldInfo:
    descriptor_raw = strip_descriptor_spaces(field.get_descriptor())
    return FieldInfo(
        name=field.get_name(),
        descriptor=normalize_descriptor(descriptor_raw),
        descriptor_raw=descriptor_raw,
        access=field.get_access_flags(),
    )


def extract_classes(dex_path, provenance, label):
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

        interfaces = sorted([strip_descriptor_spaces(i) for i in interfaces if i])

        # superclass
        try:
            superclass = strip_descriptor_spaces(cls.get_superclassname())
        except Exception:
            superclass = None

        yield ClassInfo(
            class_name=class_name,
            superclass=superclass,
            interfaces=frozenset(interfaces),
            provenance=provenance,
            fields=fields,
            methods=methods,
        )


def extract_from_dex(paths, label) -> list[ClassInfo]:
    classes = []
    for p in paths:
        p = Path(p)
        if not p.is_file():
            sys.exit(f"ERROR: DEX not found: {p}")
        classes.extend(extract_classes(p, p.name, label=label))
    print(f"[+] Extracting {label} features complete\n")
    return classes

#!/usr/bin/env python3

import rosal


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
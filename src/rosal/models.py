#!/usr/bin/env python3

import rosal
from dataclasses import dataclass
from rosal.utils import class_package, is_platform_ref, descriptor_is_level_a

@dataclass(frozen=True)
class MethodInfo:
    name: str
    descriptor: str  
    descriptor_raw: str        
    access: int
    n_insns: int
    has_body: bool
    strings: frozenset[str]
    numbers: frozenset
    api_refs: frozenset[str]
    class_refs: frozenset[str]
    invokes: frozenset[str]

    def is_concrete(self) -> bool:
        return self.name not in rosal.CONSTRUCTOR_NAMES and self.has_body

    def has_anchor_evidence(self) -> bool:
        return bool(
            self.strings or self.api_refs or self.class_refs
            or self.invokes
        )

    def anchor_key(self):
        return (
            self.descriptor,
            self.access,
            self.n_insns,
            tuple(sorted(self.strings)),
            tuple(sorted(self.numbers)),
            tuple(sorted(self.api_refs)),
            tuple(sorted(self.class_refs)),
            tuple(sorted(self.invokes)),
        )


@dataclass(frozen=True)
class FieldInfo:
    name: str
    descriptor: str       
    descriptor_raw: str    
    access: int

    def has_anchor_evidence(self) -> bool:
        return descriptor_is_level_a(self.descriptor)

    def anchor_key(self):
        return (self.descriptor, self.access)


@dataclass
class ClassInfo:
    class_name: str
    superclass: str | None
    interfaces: frozenset
    methods: list[MethodInfo]
    fields: list[FieldInfo]
    provenance: str | None = None

    @property
    def package(self) -> str:
        return class_package(self.class_name)

    @property
    def platform_superclass(self):
        return self.superclass if is_platform_ref(self.superclass) else None

    @property
    def platform_interfaces(self):
        return frozenset(x for x in self.interfaces if is_platform_ref(x))

    def lookup_key(self):
        """(package, superclass)"""
        return (self.package, self.platform_superclass)
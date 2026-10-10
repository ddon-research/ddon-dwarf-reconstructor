"""Small concrete source-bound DIE graphs for declarator and scope tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TypeAttribute:
    """An attribute with an explicit value and form."""

    value: Any
    form: str = "DW_FORM_flag"


@dataclass
class TypeUnit:
    """Distinct CU identity for collision tests."""

    cu_offset: int = 0
    header: dict[str, Any] = field(default_factory=dict)


@dataclass
class TypeDie:
    """Concrete parent, child and reference relationships without mock defaults."""

    tag: str
    offset: int
    attributes: dict[str, TypeAttribute] = field(default_factory=dict)
    cu: TypeUnit | None = field(default_factory=TypeUnit)
    parent: TypeDie | None = None
    children: list[TypeDie] = field(default_factory=list)
    targets: dict[str, TypeDie | None] = field(default_factory=dict)
    dwarfinfo: Any = None
    has_children: bool = False

    def named(self, name: str) -> TypeDie:
        self.attributes["DW_AT_name"] = TypeAttribute(name.encode(), "DW_FORM_string")
        return self

    def link(self, target: TypeDie | None, attribute: str = "DW_AT_type") -> TypeDie:
        self.attributes[attribute] = TypeAttribute(
            target.offset if target is not None else 0, "DW_FORM_ref4"
        )
        self.targets[attribute] = target
        return self

    def get_DIE_from_attribute(self, attribute_name: str) -> TypeDie | None:  # noqa: N802
        return self.targets.get(attribute_name)

    def get_parent(self) -> TypeDie | None:
        return self.parent

    def iter_children(self) -> list[TypeDie]:
        return self.children

    def get_full_path(self) -> str:
        return "fixture.cpp"

    def is_null(self) -> bool:
        return False

    def __getitem__(self, attribute_name: str) -> TypeAttribute:
        return self.attributes[attribute_name]

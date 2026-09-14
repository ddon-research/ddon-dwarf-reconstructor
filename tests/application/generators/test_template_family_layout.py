"""Cross-root template ownership and publication invariants."""

from dataclasses import replace

import pytest

from ddon_dwarf_reconstructor.application.generators.dwarf_symbol_generation import _class_owners
from ddon_dwarf_reconstructor.application.generators.symbol_header_layout import (
    allocate_header_paths,
    header_groups,
    header_names_for_group,
)
from ddon_dwarf_reconstructor.application.generators.symbol_header_validation import (
    _validate_template_locations,
)
from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo, MemberInfo, TemplateTypeParam
from ddon_dwarf_reconstructor.domain.services.generation.template_families import (
    plan_template_families,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def _template(argument: str) -> ClassInfo:
    return ClassInfo(
        f"Box<{argument}>",
        8,
        [MemberInfo("data", f"{argument}*", offset=0)],
        [],
        [],
        [],
        [],
        [],
        declaration_file="Box.h",
        template_parameters=[TemplateTypeParam("T", argument)],
    )


def test_multi_root_family_has_one_path_and_no_self_include() -> None:
    infos = {"a": _template("Apple"), "b": _template("Banana")}
    origins = {"a": {"RootA"}, "b": {"RootB"}}
    planned, _families = plan_template_families(infos, origins)
    owners = _class_owners(planned, {}, origins)
    assert owners == {"a": "shared", "b": "shared"}
    paths = allocate_header_paths(header_groups(planned, owners), planned)
    assert paths == {"shared/Box.h": ("shared", ("a", "b"))}
    assert (
        header_names_for_group(
            planned, ("a", "b"), {"a": "shared/Box.h", "b": "shared/Box.h"}, "shared"
        )
        == {}
    )


def test_template_location_invariant_rejects_cross_file_duplicates() -> None:
    planned, _ = plan_template_families({"a": _template("Apple"), "b": _template("Banana")}, {})
    with pytest.raises(ValueError, match="one canonical location"):
        _validate_template_locations(
            {"a/Box.h": "class Box { };", "b/Box.h": "class Box { };"}, planned
        )


def test_same_basename_does_not_merge_unrelated_definitions() -> None:
    first = replace(
        _template("Apple"), name="First", template_parameters=[], declaration_file="one/Box.h"
    )
    second = replace(first, name="Second", declaration_file="two/Box.h")
    infos = {"a": first, "b": second}
    paths = allocate_header_paths(header_groups(infos, {"a": "shared", "b": "shared"}), infos)
    assert len(paths) == 2
    assert all(path.startswith("shared/Box-") for path in paths)

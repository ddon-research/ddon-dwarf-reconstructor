"""Tests for typed application generation contracts."""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import Mock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ddon_dwarf_reconstructor.application.generators import (
    DwarfGenerator,
    GenerationRequest,
    HeaderBundle,
)
from ddon_dwarf_reconstructor.domain.models.dwarf import TypeDeclarator


@pytest.mark.unit
def test_header_bundle_sorts_and_freezes_output_mapping() -> None:
    bundle = HeaderBundle({"z.h": "z", "a.h": "a"})

    assert isinstance(bundle.headers, MappingProxyType)
    assert list(bundle.headers) == ["a.h", "z.h"]
    assert bundle.as_dict() == {"a.h": "a", "z.h": "z"}


@pytest.mark.unit
def test_header_bundle_only_requires_one_header() -> None:
    assert HeaderBundle.single("MtObject", "header").only() == "header"
    with pytest.raises(ValueError, match="exactly one"):
        HeaderBundle({"a.h": "a", "b.h": "b"}).only()


@pytest.mark.unit
def test_generation_request_is_immutable() -> None:
    request = GenerationRequest("MtObject", full_hierarchy=True)

    with pytest.raises(AttributeError):
        request.symbol = "Other"  # type: ignore[misc]


@pytest.mark.unit
def test_dwarf_generator_bundle_selects_each_rendering_mode() -> None:
    generator = object.__new__(DwarfGenerator)
    generator.generate_header = Mock(return_value="single")
    generator.generate_complete_hierarchy_header = Mock(return_value="complete")
    generator.generate_multi_file_hierarchy = Mock(return_value={"a.h": "multi"})

    assert generator.generate_bundle(GenerationRequest("A")).as_dict() == {"A.h": "single"}
    assert generator.generate_bundle(
        GenerationRequest("A", full_hierarchy=True, single_file=True)
    ).as_dict() == {"A.h": "complete"}
    assert generator.generate_bundle(
        GenerationRequest("A", full_hierarchy=True, single_file=False)
    ).as_dict() == {"a.h": "multi"}


@pytest.mark.unit
@given(
    base=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        min_size=1,
        max_size=8,
    ),
    dimensions=st.lists(st.one_of(st.none(), st.integers(min_value=0, max_value=8)), max_size=3),
)
def test_type_declarator_rendering_preserves_array_shape(
    base: str, dimensions: list[int | None]
) -> None:
    declarator = TypeDeclarator(base_name=base, array_dimensions=tuple(dimensions))

    rendered = declarator.render()

    assert rendered.startswith(base)
    assert rendered.count("[") == len(dimensions)
    for dimension in dimensions:
        assert f"[{'' if dimension is None else dimension}]" in rendered

"""Definition signatures share the header method policy."""

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import MethodInfo, ParameterInfo
from ddon_dwarf_reconstructor.domain.services.generation.method_definition_rendering import (
    MethodDefinitionRenderingService,
)


@pytest.mark.unit
@pytest.mark.functional
def test_definition_signature_preserves_cv_ref_noexcept_and_parameters() -> None:
    method = MethodInfo(
        name="load",
        return_type="void",
        parameters=[ParameterInfo("stream", "MtStream&")],
        is_const=True,
        ref_qualifier="&&",
        is_noexcept=True,
    )

    assert (
        MethodDefinitionRenderingService.render("rLayout", method)
        == "void rLayout::load(MtStream& stream) const && noexcept"
    )


@pytest.mark.unit
@pytest.mark.functional
def test_definition_signature_handles_constructor_destructor_and_operator() -> None:
    constructor = MethodInfo("rLayout", "void", is_constructor=True)
    destructor = MethodInfo("~rLayout", "void", is_destructor=True)
    operator = MethodInfo("operator bool", "bool")

    assert MethodDefinitionRenderingService.render("rLayout", constructor) == "rLayout::rLayout()"
    assert MethodDefinitionRenderingService.render("rLayout", destructor) == "rLayout::~rLayout()"
    assert (
        MethodDefinitionRenderingService.render("rLayout", operator) == "rLayout::operator bool()"
    )

    equality = MethodInfo("operator==", "bool", parameters=[ParameterInfo("other", "rLayout&")])
    assert MethodDefinitionRenderingService.render("rLayout", equality) == (
        "bool rLayout::operator==(rLayout& other)"
    )


@pytest.mark.unit
@pytest.mark.functional
def test_definition_signature_filters_typed_artificial_parameters() -> None:
    method = MethodInfo(
        name="load",
        return_type="void",
        parameters=[
            ParameterInfo("this", "rLayout*", is_artificial=True),
            ParameterInfo("stream", "MtStream&"),
        ],
    )

    assert MethodDefinitionRenderingService.render("rLayout", method) == (
        "void rLayout::load(MtStream& stream)"
    )

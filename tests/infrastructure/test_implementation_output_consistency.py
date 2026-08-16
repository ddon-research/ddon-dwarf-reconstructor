"""Regression tests for implementation bundle consistency validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.implementation_evidence import (
    ArtifactDescriptor,
    ImplementationDiscoveryReport,
    ImplementationStatus,
    MethodAssemblyEvidence,
    SourceArtifactMetadata,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_output import (
    _validate_bundle_consistency,
)


@pytest.mark.unit
@pytest.mark.regression
def test_bundle_consistency_compares_paths_and_hashes_not_descriptor_order(
    tmp_path: Path,
) -> None:
    first = SourceArtifactMetadata(
        method_id="first",
        generation_status="generated",
        artifacts=(
            ArtifactDescriptor(kind="canonical-assembly", path="methods/z/z.s", sha256="a" * 64),
        ),
    )
    second = SourceArtifactMetadata(
        method_id="second",
        generation_status="generated",
        artifacts=(
            ArtifactDescriptor(kind="canonical-assembly", path="methods/a/a.s", sha256="b" * 64),
        ),
    )
    report = ImplementationDiscoveryReport(
        root_symbol="rLayout",
        header_bundle_sha256="header-sha",
        status=ImplementationStatus.PARTIAL,
        methods=(
            MethodAssemblyEvidence(
                owner="rLayout",
                method_name="z",
                signature="z()",
                declaration_die_offset=1,
                declaration_cu_offset=1,
                implementation_status=ImplementationStatus.NOT_OBSERVED,
                assembly_status=ImplementationStatus.NOT_OBSERVED,
                source_artifact=first,
            ),
            MethodAssemblyEvidence(
                owner="rLayout",
                method_name="a",
                signature="a()",
                declaration_die_offset=2,
                declaration_cu_offset=1,
                implementation_status=ImplementationStatus.NOT_OBSERVED,
                assembly_status=ImplementationStatus.NOT_OBSERVED,
                source_artifact=second,
            ),
        ),
    )

    _validate_bundle_consistency(
        tmp_path,
        report,
        (("methods/z/z.s", "a" * 64), ("methods/a/a.s", "b" * 64)),
    )

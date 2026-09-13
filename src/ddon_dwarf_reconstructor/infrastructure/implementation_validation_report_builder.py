"""Projection builder for source-bound implementation validation reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..domain.models.implementation_validation import (
    CompilerEvidence,
    ImplementationValidationReport,
    MethodValidationEvidence,
)
from .implementation_relocations import RELOCATION_EVALUATOR_VERSION
from .implementation_validation_tools import external_observation
from .orbis_sdk_definitions import sdk_definition_model
from .orbis_toolchain_contracts import get_toolchain_contract


def build_validation_report(
    source: Path,
    implementation_report: Path,
    source_sha256: str,
    report_sha256: str,
    status: Any,
    load_image: Any,
    segments: tuple[Any, ...],
    relocations: tuple[Any, ...],
    nids: tuple[Any, ...],
    methods: tuple[MethodValidationEvidence, ...],
    compiler: CompilerEvidence,
    probes: tuple[CompilerEvidence, ...],
    analytical_model: Any | None,
    manifest_sha: str | None,
    store_schema: str | None,
    toolchain_profile: str,
    exports: tuple[Any, ...],
    orbis_bin: Any,
    diagnostics: tuple[str, ...],
) -> ImplementationValidationReport:
    """Build the schema-4.4 report from already validated evidence dimensions."""
    return ImplementationValidationReport(
        source_path=str(source),
        source_sha256=source_sha256,
        implementation_report_path=str(implementation_report),
        implementation_report_sha256=report_sha256,
        status=status,
        load_image=load_image,
        segments=segments,
        relocations=relocations,
        nids=nids,
        methods=methods,
        compiler=compiler,
        abi_probes=probes,
        analytical_model=analytical_model,
        analytical_store_manifest_sha256=manifest_sha,
        analytical_store_schema_version=store_schema,
        sdk_definition_identity=sdk_definition_model(),
        toolchain_contract=get_toolchain_contract(toolchain_profile),
        external_tool_evidence=tuple(
            external_observation(item, manifest_path) for item, manifest_path in exports
        ),
        orbis_bin_evidence=orbis_bin,
        relocation_evaluator_version=RELOCATION_EVALUATOR_VERSION,
        nid_database_identity=_nid_database_identity(nids),
        diagnostics=diagnostics,
        validation_profile=(
            "source-bound-static-doris" if analytical_model is not None else "source-bound-static"
        ),
    )


def _nid_database_identity(nids: tuple[Any, ...]) -> str | None:
    values = {
        str(item.source)
        for item in nids
        if item.source is not None and item.source != "SCE dynamic tag payload"
    }
    return next(iter(sorted(values)), None)


__all__ = ["build_validation_report"]

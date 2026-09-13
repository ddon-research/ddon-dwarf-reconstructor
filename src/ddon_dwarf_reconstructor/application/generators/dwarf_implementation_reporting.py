"""Canonical implementation-report projection helpers."""

from __future__ import annotations

from ...domain.models.disassembly import OrbisDisassemblyReport
from ...domain.models.implementation_evidence import (
    ImplementationDiscoveryReport,
    ImplementationStatus,
    MethodAssemblyEvidence,
)
from ...domain.models.orbis_evidence import OrbisEvidenceProjection
from .generation_contracts import HeaderBundle


def implementation_report(
    root_symbol: str,
    header_bundle: HeaderBundle,
    status: ImplementationStatus,
    methods: tuple[MethodAssemblyEvidence, ...],
    disassembly: OrbisDisassemblyReport | None,
    disassembly_error: str | None,
    elf_sha256: str | None,
) -> ImplementationDiscoveryReport:
    """Build the report without copying detailed evidence into method artifacts."""
    diagnostics = (
        *(disassembly.diagnostics if disassembly else ()),
        *((disassembly_error,) if disassembly_error else ()),
    )
    report = ImplementationDiscoveryReport(
        root_symbol,
        header_bundle.sha256,
        status,
        methods,
        diagnostics=diagnostics,
        header_files=tuple(header_bundle.headers),
        elf_sha256=elf_sha256,
    )
    return (
        OrbisEvidenceProjection.from_report(disassembly).apply_to_implementation(report)
        if disassembly is not None
        else report
    )


__all__ = ["implementation_report"]

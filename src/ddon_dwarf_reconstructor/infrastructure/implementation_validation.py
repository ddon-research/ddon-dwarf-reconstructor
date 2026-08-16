"""Source-bound orchestration for static implementation validation."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from ..domain.models.analytical_dwarf import QueryResult
from ..domain.models.disassembly import OrbisToolIdentity
from ..domain.models.implementation_validation import (
    CompilerEvidence,
    ImplementationValidationReport,
    MethodValidationEvidence,
    ValidationStatus,
)
from .implementation_abi_probes import run_abi_probe_matrix
from .implementation_dwarf_context import load_doris_validation_model, sha256_file
from .implementation_load_image import read_load_image
from .implementation_method_validation import dimension_status, validate_method
from .implementation_nids import NidIndex
from .implementation_relocations import (
    RELOCATION_EVALUATOR_VERSION,
    RelocationIndex,
    evaluate_relocations,
    nid_bindings,
)
from .implementation_report_publisher import write_validation_report
from .orbis_sce_metadata import OrbisSceMetadataReader
from .orbis_sdk_definitions import sdk_definition_model

_FULL_ADDRESS_RANGE = ((0, 1 << 64),)


def validate_implementation(
    source: Path,
    implementation_report: Path,
    output_dir: Path,
    *,
    load_base: int | None = None,
    original_addresses: bool = False,
    dwarf_store: Path | None = None,
    nid_database: Path | None = None,
    nid_database_provenance: Path | None = None,
    orbis_as: Path | None = None,
    orbis_clang: Path | None = None,
    orbis_readelf: Path | None = None,
    orbis_objdump: Path | None = None,
    orbis_ld: Path | None = None,
    tool_timeout_seconds: float | None = None,
) -> ImplementationValidationReport:
    """Validate static implementation evidence and publish an atomic report."""
    source = source.resolve()
    implementation_report = implementation_report.resolve()
    output_dir = output_dir.resolve()
    raw = _read_json_object(implementation_report)
    source_sha256 = sha256_file(source)
    diagnostics = _source_binding_diagnostics(raw, source_sha256)
    store, manifest_sha, store_schema, analytical_model = load_doris_validation_model(
        dwarf_store, source, diagnostics
    )
    try:
        return _run_validation(
            source,
            implementation_report,
            output_dir,
            raw,
            source_sha256,
            sha256_file(implementation_report),
            diagnostics,
            load_base,
            original_addresses,
            nid_database,
            nid_database_provenance,
            orbis_as,
            orbis_clang,
            orbis_readelf,
            orbis_objdump,
            orbis_ld,
            tool_timeout_seconds,
            store,
            manifest_sha,
            store_schema,
            analytical_model,
        )
    finally:
        if store is not None:
            store.close()


def _run_validation(
    source: Path,
    implementation_report: Path,
    output_dir: Path,
    raw: dict[str, Any],
    source_sha256: str,
    report_sha256: str,
    diagnostics: list[str],
    load_base: int | None,
    original_addresses: bool,
    nid_database: Path | None,
    nid_database_provenance: Path | None,
    orbis_as: Path | None,
    orbis_clang: Path | None,
    orbis_readelf: Path | None,
    orbis_objdump: Path | None,
    orbis_ld: Path | None,
    tool_timeout_seconds: float | None,
    store: Any | None,
    manifest_sha: str | None,
    store_schema: str | None,
    analytical_model: Any | None,
) -> ImplementationValidationReport:
    load_image, segments = read_load_image(
        source, requested_base=load_base, original_addresses=original_addresses
    )
    metadata = _read_sce_metadata(source, source_sha256, raw, output_dir)
    relocations, nids = _relocation_evidence(
        source, load_image, segments, metadata, nid_database, nid_database_provenance, diagnostics
    )
    relocation_index = RelocationIndex.build(relocations)
    nid_index = NidIndex.build(nids)
    output_dir.mkdir(parents=True, exist_ok=True)
    probes = run_abi_probe_matrix(
        orbis_clang,
        output_dir / "abi-probes",
        readelf=orbis_readelf,
        timeout_seconds=tool_timeout_seconds,
    )
    methods, compilers = _validate_raw_methods(
        raw,
        source,
        output_dir,
        metadata.status,
        relocation_index,
        nid_index,
        probes,
        diagnostics,
        orbis_as,
        orbis_readelf,
        store,
        orbis_objdump,
        orbis_ld,
        tool_timeout_seconds,
    )
    _append_validation_diagnostics(diagnostics, load_image, metadata, methods)
    report = _build_validation_report(
        source,
        implementation_report,
        source_sha256,
        report_sha256,
        diagnostics,
        load_image,
        segments,
        relocations,
        nids,
        methods,
        compilers,
        probes,
        analytical_model,
        manifest_sha,
        store_schema,
        orbis_as,
    )
    return write_validation_report(report, output_dir)


def _validate_raw_methods(
    raw: dict[str, Any],
    source: Path,
    output_dir: Path,
    sce_status: str,
    relocations: RelocationIndex,
    nids: NidIndex,
    probes: tuple[CompilerEvidence, ...],
    diagnostics: list[str],
    assembler: Path | None,
    readelf: Path | None,
    store: Any | None,
    objdump: Path | None,
    linker: Path | None,
    timeout_seconds: float | None,
) -> tuple[tuple[MethodValidationEvidence, ...], list[CompilerEvidence]]:
    raw_methods = _method_values(raw)
    _prefetch_method_context(store, raw_methods, diagnostics)
    return _validate_methods(
        raw_methods,
        source,
        output_dir,
        sce_status,
        relocations,
        nids,
        probes,
        assembler,
        readelf,
        store,
        objdump,
        linker,
        timeout_seconds,
    )


def _build_validation_report(
    source: Path,
    implementation_report: Path,
    source_sha256: str,
    report_sha256: str,
    diagnostics: list[str],
    load_image: Any,
    segments: tuple[Any, ...],
    relocations: tuple[Any, ...],
    nids: tuple[Any, ...],
    methods: tuple[MethodValidationEvidence, ...],
    compilers: list[CompilerEvidence],
    probes: tuple[CompilerEvidence, ...],
    analytical_model: Any | None,
    manifest_sha: str | None,
    store_schema: str | None,
    assembler: Path | None,
) -> ImplementationValidationReport:
    return ImplementationValidationReport(
        source_path=str(source),
        source_sha256=source_sha256,
        implementation_report_path=str(implementation_report),
        implementation_report_sha256=report_sha256,
        status=_validation_status(load_image.status, methods, diagnostics),
        load_image=load_image,
        segments=segments,
        relocations=relocations,
        nids=nids,
        methods=methods,
        compiler=_aggregate_compiler(compilers, assembler),
        abi_probes=probes,
        analytical_model=analytical_model,
        analytical_store_manifest_sha256=manifest_sha,
        analytical_store_schema_version=store_schema,
        sdk_definition_identity=sdk_definition_model(),
        relocation_evaluator_version=RELOCATION_EVALUATOR_VERSION,
        nid_database_identity=_nid_database_identity(nids),
        diagnostics=tuple(dict.fromkeys(diagnostics)),
        validation_profile=(
            "source-bound-static-doris" if analytical_model is not None else "source-bound-static"
        ),
    )


def _append_validation_diagnostics(
    diagnostics: list[str],
    load_image: Any,
    metadata: Any,
    methods: tuple[MethodValidationEvidence, ...],
) -> None:
    diagnostics.extend(load_image.diagnostics)
    diagnostics.extend(metadata.diagnostics)
    if not methods:
        diagnostics.append(
            "CFG and external-edge parity remain not_observed without method target evidence"
        )
    diagnostics.append("live PS4 execution and behavioral equivalence remain not_observed")


def _read_sce_metadata(
    source: Path, source_sha256: str, raw: dict[str, Any], output_dir: Path
) -> Any:
    return OrbisSceMetadataReader().read(
        source,
        source_sha256=source_sha256,
        tool=_tool_identity(raw),
        cache_dir=output_dir / "sce-metadata",
        sdk_definition_identity=sdk_definition_model(),
        relevant_ranges=_FULL_ADDRESS_RANGE,
    )


def _relocation_evidence(
    source: Path,
    load_image: Any,
    segments: tuple[Any, ...],
    metadata: Any,
    nid_database: Path | None,
    nid_database_provenance: Path | None,
    diagnostics: list[str],
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    try:
        relocations, _symbols = evaluate_relocations(
            source,
            load_image,
            segments,
            metadata.relocation_entries,
            metadata.dynamic_tags,
        )
        nids = nid_bindings(
            metadata.relocation_entries,
            metadata.dynamic_tags,
            database=nid_database,
            database_provenance=nid_database_provenance,
        )
        return relocations, nids
    except (OSError, ValueError, RuntimeError) as error:
        diagnostics.append(f"relocation evidence evaluation failed: {type(error).__name__}")
        return (), ()


def _validate_methods(
    raw_methods: Sequence[dict[str, Any]],
    source: Path,
    output_dir: Path,
    sce_status: str,
    relocations: tuple[Any, ...] | RelocationIndex,
    nids: tuple[Any, ...] | NidIndex,
    probes: tuple[CompilerEvidence, ...],
    assembler: Path | None,
    readelf: Path | None,
    store: Any | None,
    objdump: Path | None = None,
    linker: Path | None = None,
    timeout_seconds: float | None = None,
) -> tuple[tuple[MethodValidationEvidence, ...], list[CompilerEvidence]]:
    methods: list[MethodValidationEvidence] = []
    compilers: list[CompilerEvidence] = []
    for index, raw_method in enumerate(raw_methods):
        method, compiler = validate_method(
            raw_method,
            index,
            source,
            output_dir / "methods",
            sce_status,
            relocations,
            nids,
            probes,
            assembler,
            readelf,
            store,
            objdump,
            linker,
            timeout_seconds,
        )
        methods.append(method)
        compilers.append(compiler)
    return tuple(methods), compilers


def _prefetch_method_context(
    store: Any | None,
    raw_methods: Sequence[dict[str, Any]],
    diagnostics: list[str],
) -> None:
    """Prime the Doris-backed context once and fail closed without N+1 fallback."""
    prefetch = getattr(store, "prefetch_method_context", None)
    if not callable(prefetch):
        return
    result = cast(QueryResult, prefetch(raw_methods))
    diagnostics.extend(result.diagnostics)


def _aggregate_compiler(values: list[CompilerEvidence], assembler: Path | None) -> CompilerEvidence:
    if not values:
        return CompilerEvidence(
            status=ValidationStatus.NOT_OBSERVED,
            profile="orbis-as",
            tool=str(assembler) if assembler is not None else None,
            diagnostics=("no method objects were requested",),
        )
    first = values[0]
    return CompilerEvidence(
        status=dimension_status(
            tuple(item.status for item in values), ValidationStatus.NOT_OBSERVED
        ),
        profile="orbis-as",
        tool=first.tool,
        tool_sha256=first.tool_sha256,
        version=first.version,
        object_metadata=first.object_metadata,
        diagnostics=tuple(diagnostic for item in values for diagnostic in item.diagnostics),
    )


def _report_status(
    load_status: ValidationStatus, methods: tuple[MethodValidationEvidence, ...]
) -> ValidationStatus:
    if load_status is ValidationStatus.FAILED:
        return ValidationStatus.FAILED
    if not methods:
        return ValidationStatus.NOT_OBSERVED
    dimensions = tuple(
        status
        for method in methods
        for status in (
            method.relocation_status,
            method.nid_status,
            method.abi.status,
            method.effects.status,
            method.compiler.status,
            method.parity.status,
        )
    )
    return (
        ValidationStatus.FAILED
        if ValidationStatus.FAILED in dimensions
        else (
            ValidationStatus.OBSERVED
            if dimensions and all(item is ValidationStatus.OBSERVED for item in dimensions)
            else ValidationStatus.PARTIAL
        )
    )


def _validation_status(
    load_status: ValidationStatus,
    methods: tuple[MethodValidationEvidence, ...],
    diagnostics: list[str],
) -> ValidationStatus:
    status = _report_status(load_status, methods)
    if any("hash does not match source" in item for item in diagnostics):
        return ValidationStatus.FAILED
    return status


def resolve_sdk_tool(sdk_root: Path | None, name: str) -> Path | None:
    """Resolve an explicitly selected SDK tool without copying SDK content."""
    roots: list[Path] = []
    if sdk_root is not None:
        roots.append(sdk_root)
    environment_root = os.environ.get("ORBIS_SDK_ROOT")
    if environment_root:
        roots.append(Path(environment_root))
    roots.append(Path(r"D:\SCE\ORBIS SDKs\8.000"))
    for root in roots:
        for candidate in (
            root / "host_tools" / "bin" / name,
            root / "host_tools" / "bin" / f"{name}.exe",
        ):
            if candidate.exists():
                return candidate.resolve()
    return None


def _nid_database_identity(nids: tuple[Any, ...]) -> str | None:
    values = {
        str(item.source)
        for item in nids
        if item.source is not None and item.source != "SCE dynamic tag payload"
    }
    return next(iter(sorted(values)), None)


def _method_values(raw: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple(item for item in _list_value(raw.get("methods")) if isinstance(item, dict))


def _tool_identity(raw: dict[str, Any]) -> Any:
    value = raw.get("tool")
    if not isinstance(value, dict):
        return OrbisToolIdentity("unavailable", "unavailable", "unavailable")
    return OrbisToolIdentity(
        str(value.get("executable_sha256", "unavailable")),
        str(value.get("version", "unavailable")),
        str(value.get("target", "unavailable")),
    )


def _source_binding_diagnostics(raw: dict[str, Any], source_sha256: str) -> list[str]:
    expected = raw.get("elf_sha256")
    if expected is None:
        return ["implementation report does not carry an ELF source hash"]
    return (
        []
        if str(expected) == source_sha256
        else ["implementation report ELF hash does not match source"]
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("implementation report must be a JSON object")
    return value


def _list_value(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


__all__ = ["resolve_sdk_tool", "validate_implementation", "write_validation_report"]

"""Versioned flat publication for one generated PS4 symbol request."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ..application.generators.generation_contracts import SymbolExtractionResult
from ..core.content_hash import sha256_text
from ..core.platform import ELFPlatform
from ..domain.models.disassembly import OrbisInstruction
from ..domain.models.implementation_evidence import (
    ImplementationDiscoveryReport,
    MethodAssemblyEvidence,
)
from .artifact_io import safe_relative_path
from .assembly_method_output import stage_method_file
from .implementation_assembler import assemble_canonical_source
from .implementation_assembly_source import canonical_assembly_source
from .symbol_output_methods import method_class_key, method_owner, method_sort_key, stable_method_id

_VERSION_RE = re.compile(r"(?<!\d)(?P<version>\d{8})(?!\d)")


@dataclass(frozen=True, slots=True)
class ClientVersion:
    value: str
    source: str
    diagnostics: tuple[str, ...] = ()


def infer_client_version(elf_path: Path) -> ClientVersion:
    """Infer one unambiguous eight-digit client token, otherwise use ``unknown``."""
    filename_versions, parent_versions = _path_versions(elf_path)
    versions = tuple(sorted(filename_versions | parent_versions))
    if len(versions) == 1:
        return ClientVersion(
            versions[0], _version_source(versions[0], filename_versions, parent_versions)
        )
    if not versions:
        return ClientVersion("unknown", "unknown", ("no eight-digit client version in ELF path",))
    return ClientVersion(
        "unknown",
        "unknown",
        (f"ambiguous client versions in ELF path: {', '.join(versions)}",),
    )


def _path_versions(elf_path: Path) -> tuple[set[str], set[str]]:
    filename_versions = {match.group("version") for match in _VERSION_RE.finditer(elf_path.name)}
    parent_versions = {
        match.group("version")
        for segment in elf_path.parent.parts
        for match in _VERSION_RE.finditer(segment)
    }
    return filename_versions, parent_versions


def _version_source(version: str, filename_versions: set[str], parent_versions: set[str]) -> str:
    if version in filename_versions and version in parent_versions:
        return "filename+parent-path"
    return "filename" if version in filename_versions else "parent-path"


class SymbolPublisher:
    MANIFEST_NAME = "symbols.manifest.json"
    REPORT_NAME = "implementation-report.json"
    SCHEMA_VERSION = "symbol-artifacts/2"
    ASM_PROFILE = "ida-evidence/1"
    # Bump the artifact producer whenever C++-observable template, scope, or
    # callable rendering semantics change.  Existing bundles remain valid
    # historical evidence but must not be reused as current output.
    PRODUCER_ID = "ddon-dwarf-reconstructor.symbols.compilation-repair-v15"

    def __init__(self, assembler: Path | None = None) -> None:
        self.assembler = assembler

    def publish(
        self,
        output_root: Path,
        platform: ELFPlatform,
        elf_path: Path,
        source_sha256: str,
        symbols: SymbolExtractionResult,
        report: ImplementationDiscoveryReport | None = None,
        *,
        emit_assembly: bool = False,
        emit_sources: bool = False,
        generate_context: bool = True,
    ) -> Path:
        version = infer_client_version(elf_path)
        target = output_root / f"{platform.value}-{version.value}"
        stage = output_root / f".{target.name}.staging-{uuid4().hex}"
        stage.mkdir(parents=True, exist_ok=False)
        try:
            self._stage_headers(stage, symbols)
            method_files = (
                self._stage_assembly(
                    stage,
                    symbols,
                    report,
                    emit_sources=emit_sources,
                    emit_objects=generate_context,
                )
                if emit_assembly
                else {}
            )
            report_path = self._stage_report(stage, report) if generate_context else None
            report_sha256 = (
                _sha256_bytes((stage / report_path).read_bytes())
                if report_path is not None
                else None
            )
            report_byte_length = (
                (stage / report_path).stat().st_size if report_path is not None else None
            )
            if generate_context:
                manifest = self._manifest(
                    platform,
                    elf_path,
                    source_sha256,
                    version,
                    symbols,
                    report,
                    method_files,
                    report_path,
                    report_sha256,
                    report_byte_length,
                )
                _write_text(
                    stage / self.MANIFEST_NAME,
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                )
            _commit_directory(stage, target)
            return target
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise

    @staticmethod
    def _stage_headers(stage: Path, symbols: SymbolExtractionResult) -> None:
        for relative, content in sorted(symbols.headers.items()):
            _write_text(stage / safe_relative_path(Path(relative)), content)

    def _stage_assembly(
        self,
        stage: Path,
        symbols: SymbolExtractionResult,
        report: ImplementationDiscoveryReport | None,
        *,
        emit_sources: bool,
        emit_objects: bool,
    ) -> dict[str, dict[str, object]]:
        if report is None:
            return {}
        files: dict[str, dict[str, object]] = {}
        seen: dict[str, str] = {}
        for method in sorted(report.methods, key=method_sort_key):
            if not method.instructions:
                continue
            method_id = stable_method_id(method)
            content = render_ida_assembly(method, method_id)
            owner = method_owner(symbols, method)
            relative = (
                Path(_safe_component(owner)) / f"{method_id}.asm"
                if owner != "shared"
                else Path("shared") / f"{method_id}.asm"
            ).as_posix()
            previous = seen.get(relative)
            if previous is not None and previous != content:
                raise ValueError(f"Conflicting symbol assembly artifact: {relative}")
            if previous is not None:
                continue
            seen[relative] = content
            _write_text(stage / relative, content)
            class_key = method_class_key(symbols, method)
            files[relative] = {
                "kind": "asm",
                "owner": owner,
                "method_id": method_id,
                "roots": list(symbols.class_origins.get(class_key, ()))
                if class_key is not None
                else [],
                "sha256": sha256_text(content),
                "bytes": len(content.encode("utf-8")),
                "status": method.assembly_status.value,
            }
            if emit_sources:
                self._stage_canonical_sources(
                    stage,
                    files,
                    seen,
                    owner,
                    method_id,
                    method,
                    emit_object=emit_objects,
                )
        return files

    def _stage_canonical_sources(
        self,
        stage: Path,
        files: dict[str, dict[str, object]],
        seen: dict[str, str],
        owner: str,
        method_id: str,
        method: MethodAssemblyEvidence,
        *,
        emit_object: bool,
    ) -> None:
        assembly, diagnostics = canonical_assembly_source(
            method_id,
            method.instructions,
            expected_start=method.selected_function_address,
            expected_size=method.selected_function_size,
        )
        if assembly is None:
            return
        owner_directory = Path("shared") if owner == "shared" else Path(_safe_component(owner))
        stage_method_file(
            stage,
            files,
            seen,
            owner_directory / f"{method_id}.s",
            assembly,
            "canonical-assembly",
            owner,
            method_id,
            diagnostics,
        )
        if emit_object:
            object_bytes, object_diagnostics = assemble_canonical_source(
                method_id, assembly, self.assembler
            )
            if object_bytes is not None:
                stage_method_file(
                    stage,
                    files,
                    seen,
                    owner_directory / f"{method_id}.o",
                    object_bytes,
                    "object",
                    owner,
                    method_id,
                    object_diagnostics,
                )

    @staticmethod
    def _stage_report(stage: Path, report: ImplementationDiscoveryReport | None) -> str | None:
        if report is None:
            return None
        _write_text(
            stage / SymbolPublisher.REPORT_NAME,
            json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        )
        return SymbolPublisher.REPORT_NAME

    def _manifest(
        self,
        platform: ELFPlatform,
        elf_path: Path,
        source_sha256: str,
        version: ClientVersion,
        symbols: SymbolExtractionResult,
        report: ImplementationDiscoveryReport | None,
        method_files: dict[str, dict[str, object]],
        report_path: str | None,
        report_sha256: str | None,
        report_byte_length: int | None,
    ) -> dict[str, object]:
        header_files = _header_file_hashes(symbols)
        file_hashes = _file_hashes(
            header_files, method_files, report_path, report_sha256, report_byte_length
        )
        return {
            "schema_version": self.SCHEMA_VERSION,
            "artifact_profile": self.ASM_PROFILE,
            "producer": self.PRODUCER_ID,
            "platform": platform.value,
            "client_version": version.value,
            "client_version_source": version.source,
            "client_version_diagnostics": list(version.diagnostics),
            "source": {"path": str(elf_path), "sha256": source_sha256},
            "input_list_sha256": sha256_text("\n".join(symbols.requested_symbols) + "\n"),
            "configuration": dict(sorted(symbols.configuration.items())),
            "requested_symbols": list(symbols.requested_symbols),
            "roots": _root_manifest(symbols),
            "header_bundle_sha256": symbols.header_bundle.sha256,
            "header_count": symbols.header_count,
            "class_count": symbols.class_count,
            "shared_header_count": sum(
                owner == "shared" for owner in symbols.header_owners.values()
            ),
            "headers": _header_manifest(symbols),
            "file_count": len(file_hashes),
            "file_hashes": dict(sorted(file_hashes.items())),
            "class_owners": dict(sorted(symbols.class_owners.items())),
            "class_origins": {
                name: list(origins) for name, origins in sorted(symbols.class_origins.items())
            },
            "class_identities": dict(sorted(symbols.class_identities.items())),
            "enum_origins": {
                name: list(origins) for name, origins in sorted(symbols.enum_origins.items())
            },
            "class_aliases": {
                name: list(aliases) for name, aliases in sorted(symbols.class_aliases.items())
            },
            **_diagnostic_manifest(symbols.diagnostics),
            "implementation": _implementation_manifest(
                report, method_files, report_path, report_sha256
            ),
        }


def _header_file_hashes(symbols: SymbolExtractionResult) -> dict[str, dict[str, object]]:
    return {
        path: {
            "kind": "header",
            "sha256": sha256_text(content),
            "bytes": len(content.encode("utf-8")),
        }
        for path, content in sorted(symbols.headers.items())
    }


def _file_hashes(
    header_files: dict[str, dict[str, object]],
    method_files: dict[str, dict[str, object]],
    report_path: str | None,
    report_sha256: str | None,
    report_byte_length: int | None,
) -> dict[str, dict[str, object]]:
    file_hashes: dict[str, dict[str, object]] = dict(header_files)
    file_hashes.update(
        {
            path: {key: value for key, value in descriptor.items() if key != "roots"}
            for path, descriptor in method_files.items()
        }
    )
    if report_path is not None and report_sha256 is not None:
        file_hashes[report_path] = {
            "kind": "implementation-report",
            "sha256": report_sha256,
            "bytes": report_byte_length,
        }
    return file_hashes


def _root_manifest(symbols: SymbolExtractionResult) -> dict[str, dict[str, object]]:
    return {
        root: {
            "status": symbols.root_statuses.get(root, "not_observed"),
            "header_count": sum(
                root in symbols.roots_for_header(path) for path in symbols.header_owners
            ),
        }
        for root in symbols.requested_symbols
    }


def _header_manifest(symbols: SymbolExtractionResult) -> dict[str, dict[str, object]]:
    return {
        path: {
            "owner": symbols.header_owners[path],
            "classes": list(symbols.header_classes[path]),
            "enums": list(symbols.header_enums.get(path, ())),
            "sha256": sha256_text(content),
            "bytes": len(content.encode("utf-8")),
        }
        for path, content in sorted(symbols.headers.items())
    }


def _diagnostic_manifest(diagnostics: tuple[str, ...]) -> dict[str, list[str]]:
    return {
        "diagnostics": list(diagnostics),
        "unresolved_diagnostics": [
            diagnostic
            for diagnostic in diagnostics
            if any(
                marker in diagnostic
                for marker in ("unresolved", "declaration-only", "not reachable")
            )
        ],
        "conflict_diagnostics": [
            diagnostic for diagnostic in diagnostics if "conflict" in diagnostic
        ],
    }


def _implementation_manifest(
    report: ImplementationDiscoveryReport | None,
    method_files: dict[str, dict[str, object]],
    report_path: str | None,
    report_sha256: str | None,
) -> dict[str, object]:
    return {
        "report_path": report_path,
        "report_sha256": report_sha256,
        "status": report.status.value if report is not None else "not_observed",
        "method_count": len(report.methods) if report is not None else 0,
        "assembly_file_count": sum(item.get("kind") == "asm" for item in method_files.values()),
        "source_file_count": sum(
            item.get("kind") in {"canonical-assembly", "object"} for item in method_files.values()
        ),
        "files": dict(sorted(method_files.items())),
    }


def render_ida_assembly(method: MethodAssemblyEvidence, method_id: str) -> str:
    lines = _ida_prologue(method, method_id)
    previous_source: tuple[str | None, int | None, int | None] = (None, None, None)
    for instruction in method.instructions:
        annotations, previous_source = _instruction_annotations(instruction, previous_source)
        lines.extend(annotations)
        lines.append(_instruction_line(instruction))
    lines.append("; ============================================================")
    return "\n".join(lines) + "\n"


def _ida_prologue(method: MethodAssemblyEvidence, method_id: str) -> list[str]:
    first_instruction = method.instructions[0] if method.instructions else None
    lines = [
        "; ============================================================",
        f"; function: {method.definition_signature or method.signature}",
        f"; method_signature: {method.signature}",
        f"; definition_signature: {method.definition_signature or 'unknown'}",
        f"; signature: {method.signature}",
        f"; pseudo_symbol: {method_id}",
        f"; symbol: {method.selected_function_name or 'unknown'}",
        f"; address: {_hex(method.selected_function_address)}",
        f"; end: {_hex(_function_end(method))}",
        f"; size: {method.selected_function_size or 'unknown'}",
        f"; implementation_status: {method.implementation_status.value}",
        f"; assembly_status: {method.assembly_status.value}",
        f"; file_offset: {_hex(first_instruction.file_offset if first_instruction else None)}",
        f"; source_location: {_source_location(first_instruction) or 'unknown'}",
        f"; evidence_status: {method.assembly_status.value}",
    ]
    if method.dwarf_context is None:
        lines.append("; type_context: not_observed")
    else:
        lines.append("; type_context: source-bound")
        lines.extend(
            f"; abi.{key}: {json.dumps(value, sort_keys=True, default=str)}"
            for key, value in sorted(method.dwarf_context.abi_facts.items())
        )
    lines.append("; ============================================================")
    return lines


def _instruction_annotations(
    instruction: OrbisInstruction,
    previous_source: tuple[str | None, int | None, int | None],
) -> tuple[list[str], tuple[str | None, int | None, int | None]]:
    source = (instruction.source_file, instruction.source_line, instruction.source_discriminator)
    lines: list[str] = []
    if source != previous_source and source[0] is not None and source[1] is not None:
        suffix = f" (discriminator {source[2]})" if source[2] is not None else ""
        lines.append(f"; source: {source[0]}:{source[1]}{suffix}")
        previous_source = source
    lines.extend(_call_annotations(instruction))
    return lines, previous_source


def _call_annotations(instruction: OrbisInstruction) -> list[str]:
    lines: list[str] = []
    emitted_targets: set[str] = set()
    for reference in instruction.references:
        if "call" not in reference.kind:
            continue
        target = reference.resolved_name or _hex(reference.address)
        emitted_targets.add(target)
        lines.append(f"; pseudo_call: {target} ({reference.resolution_status})")
    inferred_target = instruction.call_target_name or _hex(instruction.call_target_address)
    if "call" in instruction.mnemonic.lower() and inferred_target not in emitted_targets:
        lines.append(f"; pseudo_call: {inferred_target} (inferred)")
    return lines


def _instruction_line(instruction: OrbisInstruction) -> str:
    if instruction.raw_line and not _looks_like_source_line(instruction.raw_line):
        return instruction.raw_line.rstrip()
    operands = f" {instruction.operands}" if instruction.operands else ""
    return f"{instruction.address:016x}: {instruction.raw_bytes} {instruction.mnemonic}{operands}"


def _looks_like_source_line(value: str) -> bool:
    stripped = value.strip()
    if stripped.startswith(";"):
        return False
    return (
        re.fullmatch(
            r"(?:[A-Za-z]:[\\/]|/|\.{0,2}[\\/])?.+:\d+"
            r"(?:\s+\(discriminator\s+\d+\))?",
            stripped,
        )
        is not None
    )


def _source_location(instruction: OrbisInstruction | None) -> str | None:
    if instruction is None or instruction.source_file is None or instruction.source_line is None:
        return None
    suffix = (
        f" (discriminator {instruction.source_discriminator})"
        if instruction.source_discriminator is not None
        else ""
    )
    return f"{instruction.source_file}:{instruction.source_line}{suffix}"


def _function_end(method: MethodAssemblyEvidence) -> int | None:
    return (
        None
        if method.selected_function_address is None or method.selected_function_size is None
        else method.selected_function_address + method.selected_function_size
    )


def _hex(value: int | None) -> str:
    return f"0x{value:x}" if value is not None else "unknown"


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-") or "artifact"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _commit_directory(stage: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if target.exists():
        backup = target.parent / f".{target.name}.backup-{uuid4().hex}"
        os.replace(target, backup)
    try:
        os.replace(stage, target)
    except Exception:
        if backup is not None and not target.exists():
            os.replace(backup, target)
        raise
    else:
        if backup is not None and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


__all__ = ["ClientVersion", "SymbolPublisher", "infer_client_version", "render_ida_assembly"]

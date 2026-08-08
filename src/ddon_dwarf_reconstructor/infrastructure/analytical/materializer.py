"""One-pass pyelftools producer for the analytical DWARF store."""

from __future__ import annotations

import gc
import hashlib
import json
import logging
import os
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, BinaryIO

from ...core.observability import get_logger, log_event
from ...domain.models.analytical_dwarf import (
    DwarfMaterializationRequest,
    DwarfRecordKind,
    MaterializationManifest,
)
from ...infrastructure.artifacts import SourceIdentityCatalog
from ..elf_session import ElfDwarfSession
from .dwarf_recovery import DwarfRecoveryReport, apply_source_bound_dwarf_recovery
from .manifest import (
    has_parser_diagnostics,
    has_unapplied_source_recovery,
    load_manifest,
    validate_manifest_files,
    validate_schema_version,
)
from .materialization_manifest import build_checkpoint_manifest, build_manifest
from .record_sink import RecordWriter
from .semantic_emitter import DwarfSemanticEmitter
from .unit_emitter import DwarfUnitEmitter

_DEBUG_PREFIXES = (".debug_", ".zdebug_")
_DEBUG_SECTION_NAMES = (".eh_frame", ".eh_frame_hdr", ".gnu_debuglink", ".gnu_debugaltlink")
_DEFAULT_SOURCE_IDENTITY = "unknown"
_MAX_INLINE_VALUE_BYTES = 1024 * 1024


class DwarfMaterializer:
    """Materialize one ELF without retaining the full DWARF graph."""

    def __init__(self, identity_catalog: SourceIdentityCatalog | None = None) -> None:
        self.identity_catalog = identity_catalog or SourceIdentityCatalog()
        self.last_manifest_path: Path | None = None
        self.last_checkpoint_manifest_path: Path | None = None
        self.cu_passes = 0
        self._logger = get_logger(__name__)

    def materialize(self, request: DwarfMaterializationRequest) -> MaterializationManifest:
        """Publish a complete typed store or fail without replacing an existing store."""
        source_path = request.source_path.resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        identity = self.identity_catalog.identify(source_path)
        self.last_checkpoint_manifest_path = None
        request.output_dir.mkdir(parents=True, exist_ok=True)
        store_dir = request.output_dir / f"store-{identity.sha256[:16]}"
        existing = self._existing_store(store_dir, identity.sha256)
        if existing is not None:
            existing = self._ensure_requested_projections(existing, request, store_dir)
            self.last_manifest_path = store_dir / "manifest.json"
            return existing
        if store_dir.exists():
            raise ValueError(f"Refusing to replace incomplete analytical store: {store_dir}")
        temporary = Path(tempfile.mkdtemp(prefix=f".{store_dir.name}-", dir=request.output_dir))
        try:
            manifest = self._write_store(request, source_path, identity, temporary)
            os.replace(temporary, store_dir)
            self.last_manifest_path = store_dir / "manifest.json"
            return manifest
        except BaseException:
            if request.checkpoint_every_cus is None or not any(temporary.glob("checkpoint.json")):
                shutil.rmtree(temporary, ignore_errors=True)
            raise

    def _existing_store(
        self, store_dir: Path, source_sha256: str
    ) -> MaterializationManifest | None:
        manifest_path = store_dir / "manifest.json"
        if not manifest_path.is_file():
            return None
        manifest = load_manifest(manifest_path)
        if manifest.source_identity.sha256 != source_sha256 or manifest.status != "complete":
            raise ValueError(f"Analytical store identity/status mismatch: {manifest_path}")
        validate_schema_version(manifest, allow_incomplete=False)
        if has_parser_diagnostics(manifest) or has_unapplied_source_recovery(manifest):
            raise ValueError(f"Analytical store has partial DWARF parsing: {manifest_path}")
        validate_manifest_files(
            manifest_path,
            manifest,
            verify_hashes=True,
            verify_payload=True,
        )
        return manifest

    @staticmethod
    def _ensure_requested_projections(
        manifest: MaterializationManifest,
        request: DwarfMaterializationRequest,
        store_dir: Path,
    ) -> MaterializationManifest:
        """Add requested projections to an already complete canonical store."""
        manifest_path = store_dir / "manifest.json"
        current = manifest
        if request.write_jsonl and "records" not in current.files:
            raise ValueError(
                "Existing direct Parquet store has no JSONL audit projection; "
                "publish it to a new output directory with --write-jsonl"
            )
        if request.write_parquet and "parquet" not in current.files:
            from .parquet import ParquetPublisher, describe_parquet_files

            publisher = ParquetPublisher()
            publisher.publish_from_manifest_path(manifest_path)
            current = replace(
                current,
                files={**current.files, "parquet": "parquet"},
                configuration={
                    **current.configuration,
                    "write_parquet": True,
                    "parquet_writer_metrics": publisher.last_writer_metrics,
                },
                artifacts=describe_parquet_files(store_dir),
            )
            _write_json_atomic(manifest_path, current.to_dict())
        return current

    def _write_store(
        self,
        request: DwarfMaterializationRequest,
        source_path: Path,
        identity: Any,
        store_dir: Path,
    ) -> MaterializationManifest:
        raw_dir = store_dir / "raw_sections"
        raw_values_dir = store_dir / "raw_values"
        raw_dir.mkdir(parents=True)
        raw_values_dir.mkdir(parents=True)
        parquet_sink = _parquet_sink(request, store_dir)
        writer = RecordWriter(_records_path(request, store_dir), parquet_sink)
        self.cu_passes = 0
        try:
            platform, section_names, parse_error_count, recovery = self._produce(
                source_path,
                identity,
                raw_dir,
                raw_values_dir,
                writer,
                request,
                store_dir,
            )
        except BaseException:
            writer.abort()
            raise
        else:
            writer.close()
        manifest = build_manifest(
            request,
            source_path,
            identity,
            platform,
            section_names,
            writer.counts,
            self.cu_passes,
            parquet_sink is not None,
            tuple(getattr(parquet_sink, "artifacts", ())),
            writer.writer_metrics(),
            parse_error_count,
            recovery,
        )
        if manifest.status != "complete" and parquet_sink is not None:
            set_status = getattr(parquet_sink, "set_status", None)
            if callable(set_status):
                set_status(manifest.status)
        manifest_path = store_dir / "manifest.json"
        _write_json_atomic(manifest_path, manifest.to_dict())
        manifest = _publish_projections(manifest, manifest_path, request, parquet_sink)
        _write_json_atomic(manifest_path, manifest.to_dict())
        return manifest

    def _produce(
        self,
        source_path: Path,
        identity: Any,
        raw_dir: Path,
        raw_values_dir: Path,
        writer: RecordWriter,
        request: DwarfMaterializationRequest,
        store_dir: Path,
    ) -> tuple[str, list[str], int, DwarfRecoveryReport]:
        source_id = identity.sha256
        with ElfDwarfSession(source_path) as session:
            if session.dwarf_info is None or session.elf_file is None:
                raise ValueError(f"No DWARF graph available for {source_path}")
            recovery = apply_source_bound_dwarf_recovery(session.dwarf_info, source_id)
            section_names = self._write_sections(
                session.elf_file, session.file_handle, raw_dir, writer, request, source_id
            )
            parse_error_count = self._write_units(
                session.dwarf_info,
                source_id,
                writer,
                raw_values_dir,
                request,
                store_dir,
                source_path,
                identity,
                session.platform.value,
                section_names,
                recovery,
            )
            return session.platform.value, section_names, parse_error_count, recovery

    def _write_sections(
        self,
        elf: Any,
        file_handle: BinaryIO | None,
        raw_dir: Path,
        writer: RecordWriter,
        request: DwarfMaterializationRequest,
        source_id: str,
    ) -> list[str]:
        if file_handle is None:
            raise ValueError("ELF session has no source file handle")
        names: list[str] = []
        semantic = DwarfSemanticEmitter(source_id, writer)
        for index, section in enumerate(elf.iter_sections()):
            name = getattr(section, "name", "")
            if not isinstance(name, str) or not _is_debug_section(name):
                continue
            names.append(name)
            header = getattr(section, "header", {})
            offset = _integer(header, "sh_offset", 0)
            size = _integer(header, "sh_size", 0)
            raw_name = f"{index:04d}-{_safe_name(name)}.bin"
            raw_path = raw_dir / raw_name
            digest, chunks = self._copy_raw_section(
                file_handle,
                offset,
                size,
                raw_path,
                request.raw_chunk_size,
            )
            writer.write(
                {
                    "record_type": DwarfRecordKind.SECTION.value,
                    "source_id": source_id,
                    "section_index": index,
                    "section_name": name,
                    "file_offset": offset,
                    "file_size": size,
                    "raw_path": f"raw_sections/{raw_name}",
                    "raw_sha256": digest,
                    "chunk_size": request.raw_chunk_size,
                    "chunk_count": len(chunks),
                }
            )
            semantic.write_macro_section(
                name,
                size,
                f"raw_sections/{raw_name}",
                digest,
            )
            for chunk_index, (relative_offset, chunk_size, chunk_digest) in enumerate(chunks):
                writer.write(
                    {
                        "record_type": DwarfRecordKind.RAW_CHUNK.value,
                        "source_id": source_id,
                        "section_index": index,
                        "section_name": name,
                        "raw_path": f"raw_sections/{raw_name}",
                        "chunk_index": chunk_index,
                        "byte_offset": relative_offset,
                        "byte_size": chunk_size,
                        "file_offset": offset + relative_offset,
                        "raw_sha256": chunk_digest,
                    }
                )
        return names

    @staticmethod
    def _copy_raw_section(
        file_handle: BinaryIO,
        offset: int,
        size: int,
        destination: Path,
        chunk_size: int,
    ) -> tuple[str, list[tuple[int, int, str]]]:
        digest = hashlib.sha256()
        chunks: list[tuple[int, int, str]] = []
        file_handle.seek(offset)
        remaining = size
        relative_offset = 0
        with destination.open("wb") as output:
            while remaining:
                chunk = file_handle.read(min(chunk_size, remaining))
                if not chunk:
                    raise EOFError(f"Truncated ELF section at offset 0x{offset:x}")
                output.write(chunk)
                digest.update(chunk)
                chunks.append((relative_offset, len(chunk), hashlib.sha256(chunk).hexdigest()))
                relative_offset += len(chunk)
                remaining -= len(chunk)
        return digest.hexdigest(), chunks

    def _write_units(
        self,
        dwarf_info: Any,
        source_id: str,
        writer: RecordWriter,
        raw_values_dir: Path,
        request: DwarfMaterializationRequest,
        store_dir: Path,
        source_path: Path,
        identity: Any,
        platform: str,
        section_names: list[str],
        recovery: DwarfRecoveryReport,
    ) -> int:
        emitter = DwarfUnitEmitter(source_id, writer, raw_values_dir, dwarf_info)
        parse_error_count = 0
        for cu in dwarf_info.iter_CUs():
            if request.max_cus is not None and self.cu_passes >= request.max_cus:
                break
            self.cu_passes += 1
            try:
                parse_error = emitter.write_unit(cu)
                if parse_error is not None:
                    parse_error_count += 1
                    log_event(
                        self._logger,
                        logging.WARNING,
                        "dwarf_cu_parse_partial",
                        source_sha256=source_id,
                        unit_offset=_integer(cu, "cu_offset"),
                        failure_offset=parse_error.get("failure_offset"),
                        abbrev_code=parse_error.get("abbrev_code"),
                    )
            finally:
                self._release_cu(dwarf_info, cu)
                writer.flush()
            self._complete_cu_boundary(
                request,
                store_dir,
                source_path,
                identity,
                platform,
                section_names,
                writer,
                parse_error_count,
                recovery,
            )
            if self.cu_passes % 32 == 0:
                gc.collect()
        if request.max_cus is None:
            emitter.write_global_records()
        return parse_error_count

    def _complete_cu_boundary(
        self,
        request: DwarfMaterializationRequest,
        store_dir: Path,
        source_path: Path,
        identity: Any,
        platform: str,
        section_names: list[str],
        writer: RecordWriter,
        parse_error_count: int,
        recovery: DwarfRecoveryReport,
    ) -> None:
        checkpoint_interval = request.checkpoint_every_cus
        if checkpoint_interval is not None and self.cu_passes % checkpoint_interval == 0:
            self._write_checkpoint(
                request,
                store_dir,
                source_path,
                identity,
                platform,
                section_names,
                writer,
                parse_error_count,
                recovery,
            )
            return
        rotation_interval = request.rotate_writers_every_cus
        if rotation_interval and self.cu_passes % rotation_interval == 0:
            writer.rotate()

    def _write_checkpoint(
        self,
        request: DwarfMaterializationRequest,
        store_dir: Path,
        source_path: Path,
        identity: Any,
        platform: str,
        section_names: list[str],
        writer: RecordWriter,
        parse_error_count: int,
        recovery: DwarfRecoveryReport,
    ) -> None:
        parquet_files = writer.checkpoint()
        artifacts = writer.snapshot_artifacts()
        checkpoint = build_checkpoint_manifest(
            request,
            source_path,
            identity,
            platform,
            section_names,
            writer.counts,
            self.cu_passes,
            parquet_files,
            artifacts,
            writer.writer_metrics(),
            parse_error_count,
            recovery,
        )
        checkpoint_path = store_dir / "checkpoint.json"
        _write_json_atomic(checkpoint_path, checkpoint.to_dict())
        self.last_checkpoint_manifest_path = checkpoint_path
        log_event(
            self._logger,
            logging.INFO,
            "dwarf_materialization_checkpoint",
            source_sha256=identity.sha256,
            checkpoint_path=checkpoint_path,
            cu_count=self.cu_passes,
            counts=dict(writer.counts),
        )

    @staticmethod
    def _release_cu(dwarf_info: Any, cu: Any) -> None:
        """Release pyelftools' per-CU object graph after records are emitted."""
        for attribute in ("_dielist", "_diemap"):
            cached_dies = getattr(cu, attribute, None)
            if isinstance(cached_dies, list):
                cached_dies.clear()
        for attribute in ("_cu_cache", "_cu_offsets_map"):
            cache = getattr(dwarf_info, attribute, None)
            if isinstance(cache, list):
                cache.clear()


def _records_path(request: DwarfMaterializationRequest, store_dir: Path) -> Path | None:
    return store_dir / "records.jsonl" if request.write_jsonl else None


def _parquet_sink(request: DwarfMaterializationRequest, store_dir: Path) -> Any:
    if not request.write_parquet:
        return None
    from .parquet import ParquetRecordSink

    return ParquetRecordSink(
        store_dir,
        max_open_writers=request.max_open_writers,
        layout=request.parquet_layout,
    )


def _publish_projections(
    manifest: MaterializationManifest,
    manifest_path: Path,
    request: DwarfMaterializationRequest,
    parquet_sink: Any,
) -> MaterializationManifest:
    current = manifest
    if parquet_sink is None and request.write_parquet:
        from .parquet import ParquetPublisher, describe_parquet_files

        ParquetPublisher().publish_from_manifest_path(manifest_path)
        current = replace(
            current,
            files={**current.files, "parquet": "parquet"},
            artifacts=describe_parquet_files(manifest_path.parent),
        )
    return current


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=True, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _value(container: Any, key: str) -> Any:
    try:
        return container[key]
    except KeyError, TypeError:
        return getattr(container, key, None)


def _integer(container: Any, key: str, default: int = 0) -> int:
    value = _value(container, key) if not isinstance(container, int) else container
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _integer_or_none(value: Any, key: str | None = None) -> int | None:
    candidate = _value(value, key) if key is not None else value
    return candidate if isinstance(candidate, int) and not isinstance(candidate, bool) else None


def _text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _safe_name(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "._-" else "_" for character in value
    )


def _is_debug_section(name: str) -> bool:
    return name.startswith(_DEBUG_PREFIXES) or name in _DEBUG_SECTION_NAMES

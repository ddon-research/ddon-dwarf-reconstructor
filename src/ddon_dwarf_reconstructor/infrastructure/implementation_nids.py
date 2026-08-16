"""Opaque PS4 NID evidence and explicitly attributed name resolution."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.models.disassembly import OrbisDynamicTag, OrbisRelocationEntry
from ..domain.models.implementation_validation import (
    NidBinding,
    NidResolution,
    ValidationStatus,
)

_NID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"
_NID_ALPHABET_INDEX = {character: index for index, character in enumerate(_NID_ALPHABET)}
_NID_HASH_LENGTH = 11
_COMMUNITY_AUTHORITIES = frozenset(
    {"community", "community-derived", "community_reference", "aerolib"}
)


@dataclass(frozen=True, slots=True)
class NidIndex:
    """Relocation-ID index for repeated method-local NID selection."""

    by_relocation: dict[str, tuple[tuple[int, NidBinding], ...]]

    @classmethod
    def build(cls, bindings: Iterable[NidBinding]) -> NidIndex:
        grouped: dict[str, list[tuple[int, NidBinding]]] = {}
        for index, binding in enumerate(bindings):
            if binding.relocation_id is not None:
                grouped.setdefault(binding.relocation_id, []).append((index, binding))
        return cls({key: tuple(value) for key, value in grouped.items()})

    def select(self, relocations: Iterable[Any]) -> tuple[NidBinding, ...]:
        selected: list[tuple[int, NidBinding]] = []
        for relocation in relocations:
            selected.extend(self.by_relocation.get(str(relocation.relocation_id), ()))
        selected.sort(key=lambda item: item[0])
        return tuple(binding for _index, binding in selected)


@dataclass(frozen=True, slots=True)
class _NidDatabase:
    mapping: dict[str, str]
    source: str
    authority: str
    nid_suffix: bytes | None
    diagnostics: tuple[str, ...] = ()

    @property
    def is_community(self) -> bool:
        return self.authority in _COMMUNITY_AUTHORITIES


@dataclass(frozen=True, slots=True)
class _NidEncoding:
    nid: str | None
    library_index: int | None = None
    module_index: int | None = None
    context_status: ValidationStatus = ValidationStatus.NOT_OBSERVED
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _DynamicIdentity:
    identity: int
    index: int


@dataclass(frozen=True, slots=True)
class _DynamicContext:
    libraries: tuple[_DynamicIdentity, ...]
    modules: tuple[_DynamicIdentity, ...]


def nid_bindings(
    entries: Iterable[OrbisRelocationEntry],
    dynamic_tags: tuple[OrbisDynamicTag, ...],
    *,
    database: Path | None = None,
    database_provenance: Path | None = None,
) -> tuple[NidBinding, ...]:
    """Return opaque relocation NIDs plus attributed name mappings.

    A plain JSON/text database is treated as an explicitly supplied source-bound
    mapping for compatibility with existing validation workflows. CSV input and
    mappings marked as community_reference are candidates until the mapping's
    NID hash and encoded library/module context both verify.
    """

    nid_database = _load_nid_database(database, database_provenance)
    context = _dynamic_context(dynamic_tags)
    bindings: list[NidBinding] = []
    seen: set[tuple[str | None, str | None]] = set()
    for entry in entries:
        if entry.symbol_name is None:
            continue
        encoding = _parse_nid_symbol(entry.symbol_name)
        key = (entry.relocation_id, encoding.nid)
        if key in seen:
            continue
        seen.add(key)
        bindings.append(_binding_for_entry(entry, encoding, context, nid_database))
    bindings.extend(_dynamic_identity_bindings(dynamic_tags))
    return tuple(bindings)


def _binding_for_entry(
    entry: OrbisRelocationEntry,
    encoding: _NidEncoding,
    context: _DynamicContext,
    database: _NidDatabase | None,
) -> NidBinding:
    library_id, module_id = _binding_identities(encoding, context)
    diagnostics = list(encoding.diagnostics)
    context_status, context_diagnostics = _verify_context(encoding, context)
    diagnostics.extend(context_diagnostics)
    if database is None:
        return _opaque_binding(entry, encoding, library_id, module_id, context_status, diagnostics)
    resolved = database.mapping.get(encoding.nid) if encoding.nid is not None else None
    if resolved is None:
        return _unmapped_binding(
            entry,
            encoding,
            library_id,
            module_id,
            context_status,
            diagnostics,
            database,
        )
    return _mapped_binding(
        entry,
        encoding,
        library_id,
        module_id,
        context_status,
        diagnostics,
        database,
        resolved,
    )


def _binding_identities(
    encoding: _NidEncoding,
    context: _DynamicContext,
) -> tuple[int | None, int | None]:
    library = _identity_for_index(context.libraries, encoding.library_index)
    module = _identity_for_index(context.modules, encoding.module_index)
    if library is None and context.libraries:
        library = context.libraries[0]
    if module is None and context.modules:
        module = context.modules[0]
    return (
        library.identity if library is not None else None,
        module.identity if module is not None else None,
    )


def _opaque_binding(
    entry: OrbisRelocationEntry,
    encoding: _NidEncoding,
    library_id: int | None,
    module_id: int | None,
    context_status: ValidationStatus,
    diagnostics: list[str],
) -> NidBinding:
    diagnostics.append("NID name authority was not supplied")
    return NidBinding(
        relocation_id=entry.relocation_id,
        encoded_symbol=entry.symbol_name,
        encoded_nid=encoding.nid,
        module_id=module_id,
        library_id=library_id,
        version_major=None,
        version_minor=None,
        resolved_name=None,
        source=None,
        status=ValidationStatus.NOT_OBSERVED,
        diagnostics=tuple(diagnostics),
        resolution=NidResolution.OPAQUE,
        encoded_library_index=encoding.library_index,
        encoded_module_index=encoding.module_index,
        context_status=context_status,
    )


def _unmapped_binding(
    entry: OrbisRelocationEntry,
    encoding: _NidEncoding,
    library_id: int | None,
    module_id: int | None,
    context_status: ValidationStatus,
    diagnostics: list[str],
    database: _NidDatabase,
) -> NidBinding:
    diagnostics.extend(database.diagnostics)
    diagnostics.append("NID name was not present in the supplied mapping")
    return NidBinding(
        relocation_id=entry.relocation_id,
        encoded_symbol=entry.symbol_name,
        encoded_nid=encoding.nid,
        module_id=module_id,
        library_id=library_id,
        version_major=None,
        version_minor=None,
        resolved_name=None,
        source=database.source,
        status=ValidationStatus.NOT_OBSERVED,
        diagnostics=tuple(diagnostics),
        resolution=NidResolution.OPAQUE,
        encoded_library_index=encoding.library_index,
        encoded_module_index=encoding.module_index,
        context_status=context_status,
    )


def _mapped_binding(
    entry: OrbisRelocationEntry,
    encoding: _NidEncoding,
    library_id: int | None,
    module_id: int | None,
    context_status: ValidationStatus,
    diagnostics: list[str],
    database: _NidDatabase,
    resolved: str,
) -> NidBinding:
    hash_status, hash_diagnostics = _verify_hash(encoding.nid, resolved, database.nid_suffix)
    diagnostics.extend(hash_diagnostics)
    diagnostics.extend(database.diagnostics)
    failed = ValidationStatus.FAILED in (hash_status, context_status)
    if failed:
        status = ValidationStatus.FAILED
        resolution = NidResolution.CONFLICTING
    elif database.is_community:
        verified = (
            hash_status is ValidationStatus.OBSERVED
            and context_status is ValidationStatus.OBSERVED
            and not database.diagnostics
        )
        status = ValidationStatus.OBSERVED if verified else ValidationStatus.PARTIAL
        resolution = (
            NidResolution.COMMUNITY_VERIFIED if verified else NidResolution.COMMUNITY_CANDIDATE
        )
    else:
        status = ValidationStatus.OBSERVED
        resolution = NidResolution.EXPLICIT_SOURCE_BOUND
    return NidBinding(
        relocation_id=entry.relocation_id,
        encoded_symbol=entry.symbol_name,
        encoded_nid=encoding.nid,
        module_id=module_id,
        library_id=library_id,
        version_major=None,
        version_minor=None,
        resolved_name=resolved,
        source=database.source,
        status=status,
        diagnostics=tuple(diagnostics),
        resolution=resolution,
        encoded_library_index=encoding.library_index,
        encoded_module_index=encoding.module_index,
        hash_status=hash_status,
        context_status=context_status,
    )


def _load_nid_database(
    path: Path | None,
    provenance_path: Path | None = None,
) -> _NidDatabase | None:
    if path is None:
        if provenance_path is not None:
            raise ValueError("NID provenance requires --nid-database")
        return None
    resolved_path = path.resolve()
    raw_bytes = resolved_path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    embedded_mapping, embedded_provenance = _read_database_mapping(resolved_path, raw_bytes)
    external_provenance, provenance_identity = _read_provenance(provenance_path)
    metadata = {**embedded_provenance, **external_provenance}
    expected_digest = str(metadata.get("file_sha256", metadata.get("database_sha256", "")))
    _validate_database_digest(expected_digest, digest)
    authority = _database_authority(metadata, resolved_path)
    source_parts = [f"{resolved_path}:{digest}", f"authority={authority}"]
    source_parts.extend(_source_metadata_parts(metadata))
    if provenance_identity is not None:
        source_parts.append(provenance_identity)
    return _NidDatabase(
        mapping=_normalize_mapping(embedded_mapping),
        source="|".join(source_parts),
        authority=authority,
        nid_suffix=_read_nid_suffix(metadata.get("nid_suffix_hex")),
        diagnostics=_database_diagnostics(authority, metadata, expected_digest),
    )


def _read_database_mapping(
    path: Path,
    raw_bytes: bytes,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if path.suffix.lower() != ".json":
        return _parse_text_mapping(raw_bytes.decode("utf-8")), {}
    value = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("NID JSON database must be an object mapping IDs to names")
    if not isinstance(value.get("mapping"), dict):
        return value, {}
    candidate = value.get("provenance", {})
    if candidate is not None and not isinstance(candidate, dict):
        raise ValueError("NID JSON provenance must be an object")
    return value["mapping"], candidate or {}


def _validate_database_digest(expected: str, actual: str) -> None:
    if expected and expected.lower() != actual:
        raise ValueError("NID database SHA-256 does not match its provenance manifest")


def _database_authority(metadata: Mapping[str, Any], path: Path) -> str:
    default = "community_reference" if path.suffix.lower() == ".csv" else "explicit_source_bound"
    return str(metadata.get("authority", default)).strip().lower()


def _source_metadata_parts(metadata: Mapping[str, Any]) -> list[str]:
    return [
        f"{key}={metadata[key]}" for key in ("source_url", "source_commit") if metadata.get(key)
    ]


def _database_diagnostics(
    authority: str,
    metadata: Mapping[str, Any],
    expected_digest: str,
) -> tuple[str, ...]:
    if authority not in _COMMUNITY_AUTHORITIES:
        return ()
    diagnostics: list[str] = []
    if not (metadata.get("source_url") and metadata.get("source_commit")):
        diagnostics.append("community NID mapping lacks a pinned source_url and source_commit")
    if not expected_digest:
        diagnostics.append("community NID mapping lacks a pinned file_sha256")
    return tuple(diagnostics)


def _read_provenance(path: Path | None) -> tuple[dict[str, Any], str | None]:
    if path is None:
        return {}, None
    resolved_path = path.resolve()
    raw = resolved_path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("NID provenance manifest must be a JSON object")
    digest = hashlib.sha256(raw).hexdigest()
    return value, f"provenance_path={resolved_path}|provenance_sha256={digest}"


def _parse_text_mapping(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = _mapping_fields(stripped)
        if len(fields) < 2 or not fields[0] or not fields[1]:
            raise ValueError(f"NID database line {line_number} needs an ID and name")
        _add_mapping(mapping, fields[0], " ".join(fields[1:]).strip())
    return mapping


def _mapping_fields(line: str) -> list[str]:
    if "," not in line:
        return line.split(None, 1)
    row = next(csv.reader([line]))
    return [field.strip() for field in row]


def _normalize_mapping(value: Mapping[str, Any] | None) -> dict[str, str]:
    if value is None:
        raise ValueError("NID database mapping is missing")
    mapping: dict[str, str] = {}
    for key, name in value.items():
        _add_mapping(mapping, key, str(name))
    return mapping


def _add_mapping(mapping: dict[str, str], key: str, name: str) -> None:
    nid = _encoded_nid(key)
    if nid is None:
        raise ValueError(f"invalid NID key {key!r}")
    previous = mapping.get(nid)
    if previous is not None and previous != name:
        raise ValueError(f"conflicting names for NID {nid}")
    mapping[nid] = name


def _read_nid_suffix(value: Any) -> bytes | None:
    if value in (None, ""):
        return None
    try:
        suffix = bytes.fromhex(str(value))
    except ValueError as error:
        raise ValueError("nid_suffix_hex must contain hexadecimal bytes") from error
    if len(suffix) != 16:
        raise ValueError("nid_suffix_hex must encode exactly 16 bytes")
    return suffix


def _parse_nid_symbol(symbol: str) -> _NidEncoding:
    nid = _encoded_nid(symbol)
    if len(symbol) <= _NID_HASH_LENGTH or symbol[_NID_HASH_LENGTH] != "#":
        return _NidEncoding(nid=nid)
    fields = symbol[_NID_HASH_LENGTH + 1 :].split("#")
    if len(fields) != 2 or not all(fields):
        return _NidEncoding(
            nid=nid,
            context_status=ValidationStatus.FAILED,
            diagnostics=("malformed NID library/module suffix",),
        )
    try:
        library_index = _decode_index(fields[0])
        module_index = _decode_index(fields[1])
    except ValueError as error:
        return _NidEncoding(
            nid=nid,
            context_status=ValidationStatus.FAILED,
            diagnostics=(str(error),),
        )
    return _NidEncoding(
        nid=nid,
        library_index=library_index,
        module_index=module_index,
    )


def _decode_index(value: str) -> int:
    decoded = 0
    for character in value:
        try:
            digit = _NID_ALPHABET_INDEX[character]
        except KeyError as error:
            raise ValueError(f"invalid NID context character {character!r}") from error
        decoded = decoded * len(_NID_ALPHABET) + digit
    return decoded


def _encoded_nid(symbol: str | None) -> str | None:
    if symbol is None or len(symbol) < _NID_HASH_LENGTH:
        return None
    candidate = symbol[:_NID_HASH_LENGTH]
    return candidate if all(character in _NID_ALPHABET for character in candidate) else None


def _dynamic_context(tags: tuple[OrbisDynamicTag, ...]) -> _DynamicContext:
    libraries: list[_DynamicIdentity] = []
    modules: list[_DynamicIdentity] = []
    for tag in tags:
        table_index = tag.value >> 48
        if tag.name in {"DT_SCE_IMPORT_LIB", "DT_SCE_EXPORT_LIB"}:
            libraries.append(_DynamicIdentity(table_index, table_index))
        elif tag.name in {"DT_SCE_NEEDED_MODULE", "DT_SCE_MODULE_INFO"}:
            modules.append(_DynamicIdentity(table_index, table_index))
    return _DynamicContext(tuple(libraries), tuple(modules))


def _identity_for_index(
    identities: tuple[_DynamicIdentity, ...],
    index: int | None,
) -> _DynamicIdentity | None:
    if index is None:
        return None
    return next((item for item in identities if item.index == index), None)


def _verify_context(
    encoding: _NidEncoding,
    context: _DynamicContext,
) -> tuple[ValidationStatus, tuple[str, ...]]:
    if encoding.context_status is ValidationStatus.FAILED:
        return encoding.context_status, encoding.diagnostics
    if encoding.library_index is None or encoding.module_index is None:
        return ValidationStatus.NOT_OBSERVED, ()
    library = _identity_for_index(context.libraries, encoding.library_index)
    module = _identity_for_index(context.modules, encoding.module_index)
    if library is None or module is None:
        missing = []
        if library is None:
            missing.append(f"library index {encoding.library_index}")
        if module is None:
            missing.append(f"module index {encoding.module_index}")
        return ValidationStatus.FAILED, ("NID context was not present: " + ", ".join(missing),)
    return ValidationStatus.OBSERVED, ()


def _verify_hash(
    nid: str | None,
    name: str,
    suffix: bytes | None,
) -> tuple[ValidationStatus, tuple[str, ...]]:
    if nid is None or suffix is None:
        return ValidationStatus.NOT_OBSERVED, ()
    calculated = _calculate_nid(name, suffix)
    if calculated == nid:
        return ValidationStatus.OBSERVED, ()
    return ValidationStatus.FAILED, (f"NID hash mismatch: calculated {calculated} for {name!r}",)


def _calculate_nid(name: str, suffix: bytes) -> str:
    digest = hashlib.sha1(name.encode("utf-8") + suffix).digest()
    encoded = base64.b64encode(digest[:8][::-1]).decode("ascii").rstrip("=")
    return encoded.replace("/", "-")


def _dynamic_identity_bindings(tags: tuple[OrbisDynamicTag, ...]) -> tuple[NidBinding, ...]:
    result: list[NidBinding] = []
    identity_names = {
        "DT_SCE_NEEDED_MODULE": "module",
        "DT_SCE_MODULE_INFO": "module",
        "DT_SCE_IMPORT_LIB": "library",
        "DT_SCE_EXPORT_LIB": "library",
    }
    for tag in tags:
        kind = identity_names.get(tag.name or "")
        if kind is None:
            continue
        major = (tag.value >> 32) & 0xF
        minor = (tag.value >> 40) & 0xF
        table_index = tag.value >> 48
        result.append(
            NidBinding(
                relocation_id=None,
                encoded_symbol=kind,
                encoded_nid=None,
                module_id=(tag.value >> 48) if kind == "module" else None,
                library_id=(tag.value >> 48) if kind == "library" else None,
                version_major=major,
                version_minor=minor,
                resolved_name=None,
                source="SCE dynamic tag payload",
                status=ValidationStatus.OBSERVED,
                diagnostics=(f"dynamic identity table index {table_index}",),
            )
        )
    return tuple(result)


__all__ = ["NidIndex", "nid_bindings"]

"""Deterministic method identity and ownership helpers for symbol artifacts."""

from __future__ import annotations

import re

from ..application.generators.generation_contracts import SymbolExtractionResult
from ..core.content_hash import sha256_text
from ..domain.models.implementation_evidence import MethodAssemblyEvidence


def method_owner(symbols: SymbolExtractionResult, method: MethodAssemblyEvidence) -> str:
    """Return the final resource or shared directory for one canonical method."""
    key = method_class_key(symbols, method)
    return symbols.class_owners.get(key, "shared") if key is not None else "shared"


def method_class_key(symbols: SymbolExtractionResult, method: MethodAssemblyEvidence) -> str | None:
    """Resolve method provenance, failing closed when a display name is ambiguous.

    The implementation discovery path supplies ``owner_class_key`` for every method it can
    associate with a parsed class.  Fixture, legacy, and partial evidence may omit that key;
    selecting the first class with a matching display name would silently misattribute the
    resulting assembly artifact.  An ambiguous fallback therefore returns ``None`` so the
    publisher keeps the artifact in ``shared`` and omits unverifiable root ownership.
    """
    return (
        _known_class_key(symbols, method.owner_class_key)
        or _known_class_key(symbols, method.owner)
        or _exact_class_key(symbols, method.owner)
        or _containing_class_key(symbols, method.owner)
    )


def _known_class_key(symbols: SymbolExtractionResult, candidate: str | None) -> str | None:
    if candidate is None or candidate not in symbols.class_infos:
        return None
    return candidate


def _exact_class_key(symbols: SymbolExtractionResult, owner: str) -> str | None:
    candidates = sorted(
        name
        for name, info in symbols.class_infos.items()
        if info.qualified_name == owner or info.name == owner
    )
    return candidates[0] if len(candidates) == 1 else None


def _containing_class_key(symbols: SymbolExtractionResult, owner: str) -> str | None:
    containing = sorted(
        (
            name,
            info.qualified_name or info.name,
        )
        for name, info in symbols.class_infos.items()
        if owner.startswith(f"{info.qualified_name or info.name}::")
    )
    if not containing:
        return None
    maximum_length = max(len(display_name) for _, display_name in containing)
    candidates = [name for name, display_name in containing if len(display_name) == maximum_length]
    return candidates[0] if len(candidates) == 1 else None


def stable_method_id(method: MethodAssemblyEvidence) -> str:
    """Create a stable, collision-resistant flat method filename stem."""
    identity = "|".join(
        (
            method.owner_class_key or method.owner,
            method.owner,
            method.signature,
            str(method.declaration_die_offset),
            str(method.selected_implementation_die_offset),
            str(method.selected_function_address),
        )
    )
    slug = _safe_component(f"{method.owner}-{method.method_name}")[:48]
    return f"{slug}-{sha256_text(identity)[:16]}"


def method_sort_key(method: MethodAssemblyEvidence) -> tuple[object, ...]:
    return (
        method.owner_class_key or method.owner,
        method.owner,
        method.method_name,
        method.signature,
        method.declaration_cu_offset,
        method.declaration_die_offset,
    )


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-") or "artifact"

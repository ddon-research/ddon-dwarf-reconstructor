"""Bounded, lossless JSON encoding for heterogeneous DWARF values."""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any

MAX_REPR_LENGTH = 4096


def tag_value(value: Any, *, depth: int = 0) -> Any:
    """Encode a DWARF value without silently converting it to presentation text."""
    if depth > 32:
        return {"kind": "truncated", "type": type(value).__name__}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _tag_bytes(bytes(value))
    if isinstance(value, Enum):
        return _tag_enum(value)
    if isinstance(value, Mapping):
        return _tag_mapping(value, depth)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return _tag_sequence(value, depth)
    if hasattr(value, "__dict__"):
        return _tag_object(value, depth)
    return _tag_repr(value)


def _tag_bytes(value: bytes) -> dict[str, str]:
    return {
        "kind": "bytes",
        "encoding": "base64",
        "value": base64.b64encode(value).decode("ascii"),
    }


def _tag_enum(value: Enum) -> dict[str, Any]:
    return {"kind": "enum", "type": type(value).__name__, "value": tag_value(value.value)}


def _tag_mapping(value: Mapping[Any, Any], depth: int) -> dict[str, Any]:
    items = [
        [tag_value(key, depth=depth + 1), tag_value(item, depth=depth + 1)]
        for key, item in value.items()
    ]
    return {"kind": "mapping", "items": items}


def _tag_sequence(value: Sequence[Any], depth: int) -> dict[str, Any]:
    return {
        "kind": "sequence",
        "items": [tag_value(item, depth=depth + 1) for item in value],
    }


def _tag_object(value: Any, depth: int) -> Any:
    attributes = getattr(value, "__dict__", {})
    if isinstance(attributes, dict):
        return {
            "kind": "object",
            "type": type(value).__name__,
            "attributes": tag_value(attributes, depth=depth + 1),
        }
    return _tag_repr(value)


def _tag_repr(value: Any) -> dict[str, str]:
    return {
        "kind": "repr",
        "type": type(value).__name__,
        "value": repr(value)[:MAX_REPR_LENGTH],
    }


def untag_value(value: Any) -> Any:
    """Decode values produced by :func:`tag_value` for runtime compatibility."""
    if not isinstance(value, dict) or "kind" not in value:
        return value
    kind = value.get("kind")
    if kind == "bytes" and value.get("encoding") == "base64":
        return _untag_bytes(value)
    if kind == "sequence":
        return _untag_sequence(value)
    if kind == "mapping":
        return _untag_mapping(value)
    if kind in {"enum", "repr", "truncated"}:
        return _untag_scalar(value)
    if kind == "object":
        return _untag_object(value)
    return value


def _untag_bytes(value: dict[str, Any]) -> Any:
    encoded = value.get("value")
    if not isinstance(encoded, str):
        return value
    return base64.b64decode(encoded.encode("ascii"), validate=True)


def _untag_sequence(value: dict[str, Any]) -> list[Any]:
    return [untag_value(item) for item in value.get("items", [])]


def _untag_mapping(value: dict[str, Any]) -> dict[Any, Any]:
    return {
        _hashable_key(untag_value(pair[0])): untag_value(pair[1])
        for pair in value.get("items", [])
        if isinstance(pair, list) and len(pair) == 2
    }


def _untag_scalar(value: dict[str, Any]) -> Any:
    return value.get("value", value.get("type"))


def _untag_object(value: dict[str, Any]) -> Any:
    return untag_value(value.get("attributes", {}))


def _hashable_key(value: Any) -> Any:
    """Keep decoded mapping keys usable without losing their representation."""
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value

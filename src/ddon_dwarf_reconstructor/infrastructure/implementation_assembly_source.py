"""Canonical assembly source and byte extraction for implementation evidence."""

from __future__ import annotations

from ..domain.models.disassembly import OrbisInstruction


def canonical_assembly_source(
    method_id: str,
    instructions: tuple[OrbisInstruction, ...],
    *,
    assembly_profile: str = "byte-replay",
    expected_start: int | None = None,
    expected_size: int | None = None,
) -> tuple[str | None, tuple[str, ...]]:
    """Return exact-byte GNU/Clang assembly for one observed method slice."""
    if assembly_profile not in {"byte-replay", "sectioned"}:
        return None, (f"unsupported assembly profile: {assembly_profile}",)
    raw_bytes, diagnostics = instruction_bytes(
        instructions,
        expected_start=expected_start,
        expected_size=expected_size,
    )
    if raw_bytes is None:
        return None, tuple(diagnostics)
    safe_id = safe_name(method_id)
    section = (
        ".text" if assembly_profile == "byte-replay" else f'.section .text.{safe_id},"ax",@progbits'
    )
    lines = [section, f".globl {safe_id}", f".type {safe_id}, @function", f"{safe_id}:"]
    lines.extend(
        "    .byte " + ", ".join(f"0x{value:02x}" for value in raw_bytes[offset : offset + 16])
        for offset in range(0, len(raw_bytes), 16)
    )
    lines.append(f".size {safe_id}, .-{safe_id}")
    if assembly_profile == "sectioned":
        lines.append(".function_and_data_sections")
    lines.append("")
    return "\n".join(lines), ()


def instruction_bytes(
    instructions: tuple[OrbisInstruction, ...],
    *,
    expected_start: int | None = None,
    expected_size: int | None = None,
) -> tuple[bytes | None, list[str]]:
    """Decode a complete contiguous instruction span."""
    result = bytearray()
    diagnostics: list[str] = []
    next_address = expected_start
    for instruction in instructions:
        if next_address is None:
            next_address = instruction.address
        elif instruction.address != next_address:
            diagnostics.append(
                f"instruction at 0x{instruction.address:x} is not contiguous; "
                f"expected 0x{next_address:x}"
            )
        decoded, diagnostic = _decode_raw_bytes(instruction)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            continue
        assert decoded is not None
        result.extend(decoded)
        next_address = instruction.address + len(decoded)
    if not diagnostics and expected_size is not None and len(result) != expected_size:
        diagnostics.append(
            f"instruction bytes cover {len(result)} byte(s); expected {expected_size}"
        )
    return (None, diagnostics) if diagnostics else (bytes(result), diagnostics)


def _decode_raw_bytes(instruction: OrbisInstruction) -> tuple[bytes | None, str | None]:
    value = "".join(instruction.raw_bytes.split())
    if len(value) % 2 or not value:
        return None, f"invalid raw bytes at 0x{instruction.address:x}"
    try:
        return bytes.fromhex(value), None
    except ValueError:
        return None, f"non-hex raw bytes at 0x{instruction.address:x}"


def safe_name(value: str) -> str:
    """Create a bounded assembler symbol/file stem from a method identifier."""
    result = "".join(
        character if character.isalnum() or character in "._" else "_" for character in value
    )
    return result[:160] or "method"


__all__ = ["canonical_assembly_source", "instruction_bytes", "safe_name"]

"""Typed disassembly evidence models shared across application adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import cast


@dataclass(frozen=True)
class OrbisToolIdentity:
    """Stable identity and capabilities of one Orbis objdump executable."""

    executable_sha256: str
    version: str
    target: str


@dataclass(frozen=True)
class OrbisFunctionSymbol:
    """One demangled executable function symbol."""

    address: int
    size: int
    section: str
    name: str

    @property
    def end_address(self) -> int:
        """Return the half-open end address."""
        return self.address + self.size


@dataclass(frozen=True)
class OrbisInstruction:
    """One decoded instruction with optional source and call evidence."""

    address: int
    raw_bytes: str
    mnemonic: str
    operands: str
    source_file: str | None = None
    source_line: int | None = None
    call_target_address: int | None = None
    call_target_name: str | None = None


@dataclass(frozen=True)
class OrbisFunctionDisassembly:
    """A bounded function range and every instruction decoded inside it."""

    symbol: OrbisFunctionSymbol
    instructions: tuple[OrbisInstruction, ...]


@dataclass(frozen=True)
class OrbisDisassemblyReport:
    """Content-addressed report consumed by deterministic graph export."""

    artifact_key: str
    build_root: str
    elf_sha256: str
    tool: OrbisToolIdentity
    flags: tuple[str, ...]
    parser_version: str
    functions: tuple[OrbisFunctionDisassembly, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a stable representation suitable for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> OrbisDisassemblyReport:
        """Restore a cached representation using the shared evidence model."""
        tool_value = cast(dict[str, object], value["tool"])
        function_values = cast(list[dict[str, object]], value["functions"])
        functions = tuple(
            OrbisFunctionDisassembly(
                symbol=_symbol_from_dict(cast(dict[str, object], item["symbol"])),
                instructions=tuple(
                    _instruction_from_dict(instruction)
                    for instruction in cast(list[dict[str, object]], item["instructions"])
                ),
            )
            for item in function_values
        )
        return cls(
            artifact_key=str(value["artifact_key"]),
            build_root=str(value["build_root"]),
            elf_sha256=str(value["elf_sha256"]),
            tool=OrbisToolIdentity(
                executable_sha256=str(tool_value["executable_sha256"]),
                version=str(tool_value["version"]),
                target=str(tool_value["target"]),
            ),
            flags=tuple(str(flag) for flag in cast(list[object], value["flags"])),
            parser_version=str(value["parser_version"]),
            functions=functions,
        )


def _symbol_from_dict(value: dict[str, object]) -> OrbisFunctionSymbol:
    return OrbisFunctionSymbol(
        address=_required_int(value["address"]),
        size=_required_int(value["size"]),
        section=str(value["section"]),
        name=str(value["name"]),
    )


def _instruction_from_dict(value: dict[str, object]) -> OrbisInstruction:
    return OrbisInstruction(
        address=_required_int(value["address"]),
        raw_bytes=str(value["raw_bytes"]),
        mnemonic=str(value["mnemonic"]),
        operands=str(value["operands"]),
        source_file=_optional_string(value.get("source_file")),
        source_line=_optional_int(value.get("source_line")),
        call_target_address=_optional_int(value.get("call_target_address")),
        call_target_name=_optional_string(value.get("call_target_name")),
    )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else _required_int(value)


def _required_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise TypeError(f"Expected integer evidence, got {type(value).__name__}")

"""Pure parsers for Orbis objdump text output."""

from __future__ import annotations

import json
import re
from typing import Any

from ..domain.models.disassembly import OrbisFunctionSymbol, OrbisInstruction, OrbisReference
from ..domain.models.disassembly_scope import DisassemblyTarget
from .orbis_sdk_definitions import SCE_DYNAMIC_TAG_NAMES

MAX_GROUP_GAP = 64 * 1024

_INSTRUCTION_RE = re.compile(
    r"^\s*(?P<address>[0-9a-fA-F]+):\s+"
    r"(?P<bytes>(?:[0-9a-fA-F]{2}\s+)+)"
    r"(?P<mnemonic>[^\s]+)?(?:\s+(?P<operands>.*))?$"
)
_FULL_INSTRUCTION_RE = re.compile(
    r"^\s*(?P<address>[0-9a-fA-F]+)\s+<[^>]*>"
    r"(?:\s+\(File Offset:\s*(?P<file_offset>(?:0x)?[0-9a-fA-F]+)\))?\s+"
    r"(?P<bytes>(?:[0-9a-fA-F]{2}\s+)+)(?P<mnemonic>[^\s]+)?"
    r"(?:\s+(?P<operands>.*))?$"
)
_SOURCE_RE = re.compile(
    r"^(?P<path>.+):(?P<line>[0-9]+)"
    r"(?:\s+\(discriminator\s+(?P<discriminator>[0-9]+)\))?$"
)
_TARGET_RE = re.compile(r"(?:0x)?(?P<address>[0-9a-fA-F]+)\s+<(?P<name>[^>]+)>")
_ADDRESS_RE = re.compile(r"(?:0x)?(?P<address>[0-9a-fA-F]+)")
_BRANCH_MNEMONICS = (
    "jmp",
    "ja",
    "jae",
    "jb",
    "jbe",
    "jc",
    "je",
    "jg",
    "jge",
    "jl",
    "jle",
    "jna",
    "jnae",
    "jnb",
    "jnbe",
    "jnc",
    "jne",
    "jng",
    "jnge",
    "jnl",
    "jnle",
    "jno",
    "jnp",
    "jns",
    "jnz",
    "jo",
    "jp",
    "js",
    "jz",
    "loop",
)


class OrbisObjdumpParsingMixin:
    """Parse symbols, instructions, and bounded address ranges."""

    @staticmethod
    def parse_symbols(output: str) -> tuple[OrbisFunctionSymbol, ...]:
        """Parse demangled function symbols from ``orbis-objdump -t`` output."""
        symbols: list[OrbisFunctionSymbol] = []
        for line in output.splitlines():
            parts = line.split(maxsplit=5)
            if len(parts) != 6 or parts[2] != "F":
                continue
            try:
                address = int(parts[0], 16)
                size = int(parts[4], 16)
            except ValueError:
                continue
            if size <= 0:
                continue
            symbols.append(OrbisFunctionSymbol(address, size, parts[3], parts[5].strip()))
        return tuple(sorted(set(symbols), key=lambda symbol: (symbol.address, symbol.name)))

    @staticmethod
    def select_root_symbols(
        symbols: tuple[OrbisFunctionSymbol, ...], root_symbol: str
    ) -> tuple[OrbisFunctionSymbol, ...]:
        """Select class and nested-class methods without fuzzy name matching."""
        prefix = f"{root_symbol}::"
        thunk_prefixes = ("non-virtual thunk to ", "virtual thunk to ")

        def belongs(symbol: OrbisFunctionSymbol) -> bool:
            candidate = symbol.name
            for thunk_prefix in thunk_prefixes:
                if candidate.startswith(thunk_prefix):
                    candidate = candidate[len(thunk_prefix) :]
                    break
            return candidate.startswith(prefix)

        return tuple(symbol for symbol in symbols if belongs(symbol))

    @staticmethod
    def select_target_symbols(
        symbols: tuple[OrbisFunctionSymbol, ...],
        targets: tuple[DisassemblyTarget, ...],
    ) -> tuple[OrbisFunctionSymbol, ...]:
        """Select ELF functions from explicit DWARF ranges and names.

        Selection is deliberately address-first. Names are only a bounded
        fallback for a target that has no exact/contained ELF function symbol;
        this prevents a broad class prefix from silently widening the request.
        """
        selected: dict[tuple[int, int, str, str], OrbisFunctionSymbol] = {}
        for target in targets:
            range_matches = _target_range_matches(symbols, target.ranges)
            range_matches = range_matches or _target_name_matches_all(symbols, target)
            for symbol in range_matches:
                selected[(symbol.address, symbol.size, symbol.name, symbol.section)] = symbol
        return tuple(sorted(selected.values(), key=lambda symbol: (symbol.address, symbol.name)))

    @staticmethod
    def parse_instructions(output: str) -> tuple[OrbisInstruction, ...]:
        """Parse raw instructions and attach the active objdump source location."""
        source_location: tuple[str, int, int | None, str] | None = None
        instructions: list[OrbisInstruction] = []
        for line in output.splitlines():
            parsed_source = _parse_source_location(line)
            if parsed_source is not None:
                source_location = parsed_source
                continue
            instruction = _parse_instruction(line, source_location)
            if instruction is not None:
                instructions.append(instruction)
        return tuple(instructions)

    @staticmethod
    def parse_relocations(output: str) -> tuple[OrbisReference, ...]:
        """Preserve relocation rows as additive, source-independent references."""
        references: list[OrbisReference] = []
        for line in output.splitlines():
            match = re.match(r"^\s*(?P<address>[0-9a-fA-F]+)\s+(?P<body>.+)$", line)
            if match is None or "RELOCATION" in line.upper():
                continue
            body = match.group("body").strip()
            target = _TARGET_RE.search(body)
            name = target.group("name") if target is not None else _relocation_name(body)
            references.append(
                OrbisReference(
                    kind="relocation",
                    address=int(match.group("address"), 16),
                    resolved_name=name,
                    raw_operand=line.strip(),
                    resolution_status="resolved" if name else "unresolved",
                    relocation=body,
                )
            )
        return tuple(references)

    @staticmethod
    def parse_llvm_unknown_dynamic_tags(output: str) -> tuple[int, ...]:
        """Return numeric vendor tags LLVM did not name in its JSON output."""
        tags, _ = OrbisObjdumpParsingMixin.parse_llvm_metadata(output)
        return tags

    @staticmethod
    def parse_llvm_metadata(output: str) -> tuple[tuple[int, ...], tuple[str, ...]]:
        """Parse LLVM JSON and retain diagnostics for a valid JSON prefix."""
        value, trailing = _decode_llvm_json(output)
        tags: set[int] = set()
        _collect_llvm_dynamic_tags(value, False, tags)
        diagnostics = (
            (f"LLVM metadata has trailing non-JSON output: {trailing[:200]}",) if trailing else ()
        )
        return tuple(sorted(tags)), diagnostics

    @staticmethod
    def slice_function_text(output: str, start_address: int, end_address: int) -> str:
        """Retain the original range text without manufacturing source lines."""
        selected: list[str] = []
        active = False
        for line in output.splitlines():
            parsed, _ = _parse_instruction_line(line)
            if parsed is not None:
                address = int(parsed.group("address"), 16)
                active = start_address <= address < end_address
                if active:
                    selected.append(line.rstrip("\r\n"))
                continue
            if active and (line.strip() == "" or _SOURCE_RE.fullmatch(line.strip()) is not None):
                selected.append(line.rstrip("\r\n"))
        return "\n".join(selected) + ("\n" if selected else "")

    @staticmethod
    def _group_ranges(symbols: tuple[OrbisFunctionSymbol, ...]) -> tuple[tuple[int, int], ...]:
        groups: list[tuple[int, int]] = []
        start = symbols[0].address
        stop = symbols[0].end_address
        for symbol in symbols[1:]:
            if symbol.address > stop + MAX_GROUP_GAP:
                groups.append((start, stop))
                start = symbol.address
                stop = symbol.end_address
            else:
                stop = max(stop, symbol.end_address)
        groups.append((start, stop))
        return tuple(groups)


def _parse_instruction_line(line: str) -> tuple[re.Match[str] | None, int | None]:
    full_match = _FULL_INSTRUCTION_RE.match(line)
    if full_match is not None:
        value = full_match.group("file_offset")
        return full_match, int(value, 16) if value is not None else None
    simple_match = _INSTRUCTION_RE.match(line)
    return simple_match, None


def _target_name_matches(symbol: OrbisFunctionSymbol, target: DisassemblyTarget) -> bool:
    candidates = tuple(
        value
        for value in (target.linkage_name, target.qualified_name)
        if isinstance(value, str) and value
    )
    symbol_name = symbol.name
    for candidate in candidates:
        if symbol_name == candidate or symbol_name.startswith(f"{candidate}("):
            return True
        for prefix in ("non-virtual thunk to ", "virtual thunk to "):
            if symbol_name.removeprefix(prefix) == candidate:
                return True
    return False


def _target_range_matches(
    symbols: tuple[OrbisFunctionSymbol, ...], ranges: tuple[tuple[int, int], ...]
) -> tuple[OrbisFunctionSymbol, ...]:
    exact = tuple(symbol for symbol in symbols if _has_exact_start(symbol, ranges))
    return exact or tuple(symbol for symbol in symbols if _is_contained(symbol, ranges))


def _has_exact_start(symbol: OrbisFunctionSymbol, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(symbol.address == start for start, _end in ranges)


def _is_contained(symbol: OrbisFunctionSymbol, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= symbol.address and symbol.end_address <= end for start, end in ranges)


def _target_name_matches_all(
    symbols: tuple[OrbisFunctionSymbol, ...], target: DisassemblyTarget
) -> tuple[OrbisFunctionSymbol, ...]:
    return tuple(symbol for symbol in symbols if _target_name_matches(symbol, target))


def _parse_source_location(line: str) -> tuple[str, int, int | None, str] | None:
    match = _SOURCE_RE.fullmatch(line.strip())
    if match is None:
        return None
    discriminator = match.group("discriminator")
    return (
        match.group("path"),
        int(match.group("line")),
        int(discriminator) if discriminator is not None else None,
        line.rstrip("\r\n"),
    )


def _parse_instruction(
    line: str, source_location: tuple[str, int, int | None, str] | None
) -> OrbisInstruction | None:
    match, file_offset = _parse_instruction_line(line)
    if match is None or not match.group("mnemonic"):
        return None
    mnemonic = match.group("mnemonic")
    operands = (match.group("operands") or "").strip()
    references = _instruction_references(mnemonic, operands)
    direct_call = _direct_call_reference(references)
    source_file, source_line, source_discriminator, raw_source_line = source_location or (
        None,
        None,
        None,
        None,
    )
    return OrbisInstruction(
        address=int(match.group("address"), 16),
        raw_bytes="".join(match.group("bytes").split()).lower(),
        mnemonic=mnemonic,
        operands=operands,
        source_file=source_file,
        source_line=source_line,
        source_discriminator=source_discriminator,
        raw_source_line=raw_source_line,
        file_offset=file_offset,
        call_target_address=direct_call.address if direct_call else None,
        call_target_name=direct_call.resolved_name if direct_call else None,
        references=references,
        raw_line=line.rstrip("\r\n"),
    )


def _direct_call_reference(
    references: tuple[OrbisReference, ...],
) -> OrbisReference | None:
    return next(
        (reference for reference in references if reference.kind == "direct_call"),
        None,
    )


def _instruction_references(mnemonic: str, operands: str) -> tuple[OrbisReference, ...]:
    lower_mnemonic = mnemonic.lower()
    control = _control_reference(lower_mnemonic, operands)
    if control is not None:
        return (control,)
    data = _data_reference(operands)
    if data is not None:
        return (data,)
    return ()


def _control_reference(mnemonic: str, operands: str) -> OrbisReference | None:
    is_call = mnemonic.startswith("call")
    is_branch = mnemonic.startswith(_BRANCH_MNEMONICS)
    if not is_call and not is_branch:
        return None
    address, name = _target_details(operands)
    indirect = "*" in operands
    kind = ("indirect_" if indirect else "direct_") + ("call" if is_call else "branch")
    return OrbisReference(
        kind=kind,
        address=address,
        resolved_name=name,
        raw_operand=operands,
        resolution_status="resolved" if address is not None or name else "unresolved",
    )


def _data_reference(operands: str) -> OrbisReference | None:
    address, name = _target_details(operands)
    has_memory_operand = "(" in operands or "[" in operands
    if not has_memory_operand and name is None:
        return None
    return OrbisReference(
        kind="data",
        address=address if name is not None or not has_memory_operand else None,
        resolved_name=name,
        raw_operand=operands,
        resolution_status="resolved" if address is not None or name else "unresolved",
    )


def _target_details(operands: str) -> tuple[int | None, str | None]:
    target = _TARGET_RE.search(operands)
    if target is None:
        return _numeric_target(operands), None
    return int(target.group("address"), 16), target.group("name")


def _numeric_target(operands: str) -> int | None:
    matches = list(_ADDRESS_RE.finditer(operands))
    if not matches:
        return None
    if "(" in operands or "[" in operands:
        return None
    clean = operands.lstrip("*$ ")
    return int(matches[0].group("address"), 16) if clean.startswith(matches[0].group(0)) else None


def _relocation_name(body: str) -> str | None:
    tokens = body.split()
    if not tokens:
        return None
    candidate = tokens[-1]
    if candidate in {"*ABS*", "*UND*", ""} or candidate.startswith("0x"):
        return None
    return candidate


def _collect_llvm_dynamic_tags(value: Any, in_dynamic_section: bool, result: set[int]) -> None:
    if isinstance(value, list):
        _collect_llvm_list(value, in_dynamic_section, result)
        return
    if not isinstance(value, dict):
        return
    dynamic = in_dynamic_section or "DynamicSection" in value
    if in_dynamic_section:
        _record_llvm_dynamic_tag(value.get("Tag"), result)
    for key, item in value.items():
        _collect_llvm_dynamic_tags(item, key == "DynamicSection" or dynamic, result)


def _decode_llvm_json(output: str) -> tuple[Any, str]:
    decoder = json.JSONDecoder()
    text = output.lstrip()
    try:
        value, end = decoder.raw_decode(text)
    except json.JSONDecodeError as error:
        marker = text.find("Dynamic Relocations")
        if marker < 0:
            raise ValueError(f"LLVM metadata output is not JSON: {error}") from error
        try:
            value = json.loads(text[:marker].rstrip() + "}]")
        except json.JSONDecodeError:
            raise ValueError(f"LLVM metadata output is not JSON: {error}") from error
        return value, text[marker:].strip()
    return value, text[end:].strip()


def _collect_llvm_list(values: list[Any], in_dynamic_section: bool, result: set[int]) -> None:
    for item in values:
        _collect_llvm_dynamic_tags(item, in_dynamic_section, result)


def _record_llvm_dynamic_tag(value: Any, result: set[int]) -> None:
    tag = _numeric_llvm_tag(value)
    if tag is not None and tag >= 0x61000000 and tag not in SCE_DYNAMIC_TAG_NAMES:
        result.add(tag)


def _numeric_llvm_tag(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None

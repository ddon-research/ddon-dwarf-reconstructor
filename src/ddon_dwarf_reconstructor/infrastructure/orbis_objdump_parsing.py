"""Pure parsers for Orbis objdump text output."""

from __future__ import annotations

import re

from ..domain.models.disassembly import OrbisFunctionSymbol, OrbisInstruction

MAX_GROUP_GAP = 64 * 1024

_INSTRUCTION_RE = re.compile(
    r"^\s*(?P<address>[0-9a-fA-F]+):\s+"
    r"(?P<bytes>(?:[0-9a-fA-F]{2}\s+)+)"
    r"(?P<mnemonic>[^\s]+)?(?:\s+(?P<operands>.*))?$"
)
_SOURCE_RE = re.compile(r"^(?P<path>.+):(?P<line>[0-9]+)(?:\s+\(discriminator\s+[0-9]+\))?$")
_DIRECT_TARGET_RE = re.compile(r"^(?:0x)?(?P<address>[0-9a-fA-F]+)\s+<(?P<name>[^>]+)>$")


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
    def parse_instructions(output: str) -> tuple[OrbisInstruction, ...]:
        """Parse raw instructions and attach the active objdump source location."""
        source_file: str | None = None
        source_line: int | None = None
        instructions: list[OrbisInstruction] = []
        for line in output.splitlines():
            source_match = _SOURCE_RE.fullmatch(line.strip())
            if source_match is not None:
                source_file = source_match.group("path")
                source_line = int(source_match.group("line"))
                continue
            match = _INSTRUCTION_RE.match(line)
            if match is None or not match.group("mnemonic"):
                continue
            mnemonic = match.group("mnemonic")
            operands = (match.group("operands") or "").strip()
            target_address: int | None = None
            target_name: str | None = None
            if mnemonic.startswith("call"):
                target_match = _DIRECT_TARGET_RE.fullmatch(operands)
                if target_match is not None:
                    target_address = int(target_match.group("address"), 16)
                    target_name = target_match.group("name")
            instructions.append(
                OrbisInstruction(
                    address=int(match.group("address"), 16),
                    raw_bytes="".join(match.group("bytes").split()).lower(),
                    mnemonic=mnemonic,
                    operands=operands,
                    source_file=source_file,
                    source_line=source_line,
                    call_target_address=target_address,
                    call_target_name=target_name,
                )
            )
        return tuple(instructions)

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

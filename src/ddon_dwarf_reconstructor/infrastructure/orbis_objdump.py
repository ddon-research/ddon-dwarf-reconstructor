"""Deterministic, bounded PS4 Orbis disassembly production.

The shipped PS4 ELF is not a generic host ELF.  This adapter invokes the
matching Orbis SDK objdump, converts its textual output into a versioned
machine-readable report, and retains that report in the durable artifact cache.
Human-formatted objdump output is never parsed at graph-query time.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from ..domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisFunctionDisassembly,
    OrbisFunctionSymbol,
    OrbisInstruction,
    OrbisToolIdentity,
)
from .artifacts import SourceIdentityCatalog, get_artifact_cache_dir

REPORT_SCHEMA_VERSION = "1.0"
PARSER_VERSION = "orbis-objdump-text-v1"
DISASSEMBLY_FLAGS = ("-EL", "-l", "-C", "-w", "-d")
SYMBOL_FLAGS = ("-t", "-C", "-w")
MAX_GROUP_GAP = 64 * 1024
DEFAULT_TIMEOUT_SECONDS = 120.0

_INSTRUCTION_RE = re.compile(
    r"^\s*(?P<address>[0-9a-fA-F]+):\s+"
    r"(?P<bytes>(?:[0-9a-fA-F]{2}\s+)+)"
    r"(?P<mnemonic>[^\s]+)?(?:\s+(?P<operands>.*))?$"
)
_SOURCE_RE = re.compile(r"^(?P<path>.+):(?P<line>[0-9]+)(?:\s+\(discriminator\s+[0-9]+\))?$")
_DIRECT_TARGET_RE = re.compile(r"^(?:0x)?(?P<address>[0-9a-fA-F]+)\s+<(?P<name>[^>]+)>$")


class OrbisObjdumpProducer:
    """Run and cache bounded disassembly from the PS4 SDK toolchain."""

    def __init__(
        self,
        executable: Path,
        *,
        cache_root: Path | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        identity_catalog: SourceIdentityCatalog | None = None,
    ) -> None:
        self.executable = executable.resolve()
        self.cache_root = cache_root or get_artifact_cache_dir() / "orbis-objdump-v1"
        self.timeout_seconds = timeout_seconds
        self.identity_catalog = identity_catalog or SourceIdentityCatalog()
        self.last_cache_hit = False

    def produce(self, elf_path: Path, root_symbol: str) -> OrbisDisassemblyReport:
        """Return all bounded function ranges owned by ``root_symbol``."""
        if not self.executable.is_file():
            raise ValueError(f"Orbis objdump executable not found: {self.executable}")
        if not elf_path.is_file():
            raise ValueError(f"ELF file not found: {elf_path}")

        elf_identity = self.identity_catalog.identify(elf_path)
        executable_identity = self.identity_catalog.identify(self.executable)
        version = self._read_version()
        target = self._read_target(elf_path)
        tool = OrbisToolIdentity(executable_identity.sha256, version, target)
        artifact_key = self._artifact_key(elf_identity.sha256, tool, root_symbol)
        cache_path = self.cache_root / artifact_key / "report.json"
        cached = self._load_cached(cache_path, artifact_key)
        if cached is not None:
            self.last_cache_hit = True
            return cached

        symbols = self.parse_symbols(self._run([*SYMBOL_FLAGS, str(elf_path)]))
        selected = self.select_root_symbols(symbols, root_symbol)
        if not selected:
            raise ValueError(f"No Orbis function symbols found for {root_symbol}")

        instructions: dict[int, OrbisInstruction] = {}
        for start_address, stop_address in self._group_ranges(selected):
            output = self._run(
                [
                    *DISASSEMBLY_FLAGS,
                    f"--start-address=0x{start_address:x}",
                    f"--stop-address=0x{stop_address:x}",
                    str(elf_path),
                ]
            )
            for instruction in self.parse_instructions(output):
                instructions[instruction.address] = instruction

        functions = tuple(
            OrbisFunctionDisassembly(
                symbol=symbol,
                instructions=tuple(
                    instructions[address]
                    for address in sorted(instructions)
                    if symbol.address <= address < symbol.end_address
                ),
            )
            for symbol in selected
        )
        report = OrbisDisassemblyReport(
            artifact_key=artifact_key,
            build_root=root_symbol,
            elf_sha256=elf_identity.sha256,
            tool=tool,
            flags=DISASSEMBLY_FLAGS,
            parser_version=PARSER_VERSION,
            functions=functions,
        )
        self._write_cached(cache_path, report)
        self.last_cache_hit = False
        return report

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

    def _read_version(self) -> str:
        first_line = self._run(["--version"]).splitlines()
        if not first_line:
            raise ValueError("Orbis objdump returned no version information")
        version_lines = first_line[:2]
        return " | ".join(line.strip() for line in version_lines if line.strip())

    def _read_target(self, elf_path: Path) -> str:
        output = self._run(["-f", str(elf_path)])
        match = re.search(r"file format\s+(\S+)", output)
        if match is None:
            raise ValueError("Orbis objdump did not report an ELF target")
        return match.group(1)

    def _run(self, arguments: list[str]) -> str:
        command = [str(self.executable), *arguments]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(
                f"Orbis objdump timed out after {self.timeout_seconds:g}s"
            ) from error
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic"
            raise RuntimeError(f"Orbis objdump failed ({result.returncode}): {detail}")
        return result.stdout

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

    @staticmethod
    def _artifact_key(elf_sha256: str, tool: OrbisToolIdentity, root_symbol: str) -> str:
        payload = {
            "elf_sha256": elf_sha256,
            "flags": DISASSEMBLY_FLAGS,
            "parser_version": PARSER_VERSION,
            "root_symbol": root_symbol,
            "schema_version": REPORT_SCHEMA_VERSION,
            "tool": asdict(tool),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _load_cached(path: Path, artifact_key: str) -> OrbisDisassemblyReport | None:
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("schema_version") != REPORT_SCHEMA_VERSION:
                return None
            report_value = cast(dict[str, Any], value["report"])
            if report_value.get("artifact_key") != artifact_key:
                return None
            return OrbisDisassemblyReport.from_dict(report_value)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _write_cached(path: Path, report: OrbisDisassemblyReport) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
                json.dump(
                    {"schema_version": REPORT_SCHEMA_VERSION, "report": report.to_dict()},
                    output,
                    indent=2,
                    sort_keys=True,
                )
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            temporary_path.replace(path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

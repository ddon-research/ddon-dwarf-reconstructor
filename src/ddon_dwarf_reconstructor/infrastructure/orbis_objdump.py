"""Deterministic, bounded PS4 Orbis disassembly production.

The shipped PS4 ELF is not a generic host ELF.  This adapter invokes the
matching Orbis SDK objdump, converts its textual output into a versioned
machine-readable report, and retains that report in the durable artifact cache.
Human-formatted objdump output is never parsed at graph-query time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from ..core.observability import get_logger, log_event
from ..domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisFunctionDisassembly,
    OrbisFunctionSymbol,
    OrbisInstruction,
    OrbisToolIdentity,
)
from .artifacts import SourceIdentityCatalog, get_artifact_cache_dir
from .orbis_objdump_parsing import OrbisObjdumpParsingMixin

REPORT_SCHEMA_VERSION = "1.0"
PARSER_VERSION = "orbis-objdump-text-v1"
DISASSEMBLY_FLAGS = ("-EL", "-l", "-C", "-w", "-d")
SYMBOL_FLAGS = ("-t", "-C", "-w")
DEFAULT_TIMEOUT_SECONDS = 120.0
logger = get_logger(__name__)

__all__ = ["OrbisFunctionSymbol", "OrbisObjdumpProducer"]


@dataclass(frozen=True, slots=True)
class _ProductionContext:
    """Validated, source-bound inputs for one disassembly report."""

    elf_path: Path
    root_symbol: str
    elf_sha256: str
    tool: OrbisToolIdentity
    artifact_key: str
    cache_path: Path


class OrbisObjdumpProducer(OrbisObjdumpParsingMixin):
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
        context = self._build_context(elf_path, root_symbol)
        started_at = perf_counter()
        log_event(
            logger,
            logging.INFO,
            "orbis_disassembly_started",
            elf_path=context.elf_path,
            root_symbol=context.root_symbol,
            executable=self.executable,
            cache_path=context.cache_path,
        )
        cached = self._load_cached(context.cache_path, context.artifact_key)
        if cached is not None:
            self.last_cache_hit = True
            log_event(
                logger,
                logging.DEBUG,
                "orbis_disassembly_cache_hit",
                root_symbol=context.root_symbol,
                function_count=len(cached.functions),
                cache_path=context.cache_path,
            )
            return cached
        return self._produce_uncached(context, started_at)

    def _build_context(self, elf_path: Path, root_symbol: str) -> _ProductionContext:
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
        return _ProductionContext(
            elf_path=elf_path,
            root_symbol=root_symbol,
            elf_sha256=elf_identity.sha256,
            tool=tool,
            artifact_key=artifact_key,
            cache_path=cache_path,
        )

    def _produce_uncached(
        self, context: _ProductionContext, started_at: float
    ) -> OrbisDisassemblyReport:
        symbols = self.parse_symbols(self._run([*SYMBOL_FLAGS, str(context.elf_path)]))
        selected = self.select_root_symbols(symbols, context.root_symbol)
        if not selected:
            raise ValueError(f"No Orbis function symbols found for {context.root_symbol}")
        instructions: dict[int, OrbisInstruction] = {}
        ranges = self._group_ranges(selected)
        log_event(
            logger,
            logging.DEBUG,
            "orbis_disassembly_ranges_selected",
            root_symbol=context.root_symbol,
            symbol_count=len(selected),
            range_count=len(ranges),
        )
        for start_address, stop_address in ranges:
            output = self._run(
                [
                    *DISASSEMBLY_FLAGS,
                    f"--start-address=0x{start_address:x}",
                    f"--stop-address=0x{stop_address:x}",
                    str(context.elf_path),
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
            artifact_key=context.artifact_key,
            build_root=context.root_symbol,
            elf_sha256=context.elf_sha256,
            tool=context.tool,
            flags=DISASSEMBLY_FLAGS,
            parser_version=PARSER_VERSION,
            functions=functions,
        )
        self._write_cached(context.cache_path, report)
        self.last_cache_hit = False
        log_event(
            logger,
            logging.INFO,
            "orbis_disassembly_completed",
            root_symbol=context.root_symbol,
            function_count=len(functions),
            instruction_count=len(instructions),
            cache_path=context.cache_path,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
        )
        return report

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
        log_event(
            logger,
            logging.DEBUG,
            "orbis_objdump_invoked",
            executable=self.executable,
            argument_count=len(arguments),
            operation=arguments[0] if arguments else "",
        )
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
            log_event(
                logger,
                logging.ERROR,
                "orbis_objdump_timeout",
                timeout_seconds=self.timeout_seconds,
                operation=arguments[0] if arguments else "",
                exc_info=error,
            )
            raise TimeoutError(
                f"Orbis objdump timed out after {self.timeout_seconds:g}s"
            ) from error
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic"
            log_event(
                logger,
                logging.ERROR,
                "orbis_objdump_failed",
                returncode=result.returncode,
                operation=arguments[0] if arguments else "",
                detail=detail[:500],
            )
            raise RuntimeError(f"Orbis objdump failed ({result.returncode}): {detail}")
        return result.stdout

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
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            log_event(
                logger,
                logging.WARNING,
                "orbis_disassembly_cache_invalid",
                cache_path=path,
                exc_info=error,
            )
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
            temporary_path.unlink(missing_ok=True)

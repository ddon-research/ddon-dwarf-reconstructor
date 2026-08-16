"""Application-facing port for optional executable disassembly evidence."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ..models.disassembly import OrbisDisassemblyReport
from ..models.disassembly_scope import DisassemblyRequest


class DisassemblyProducerPort(Protocol):
    """Produce deterministic disassembly evidence for an explicit source scope."""

    def produce(
        self, elf_path: Path, request: DisassemblyRequest | str
    ) -> OrbisDisassemblyReport: ...


DisassemblyProducerFactory = Callable[[Path], DisassemblyProducerPort]

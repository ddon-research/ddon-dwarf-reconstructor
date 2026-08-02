"""Compatibility façade for deterministic knowledge-graph export."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...domain.ports.source_identity import SourceHashPort
from .knowledge_export_core import KnowledgeExportCoreMixin
from .knowledge_export_disassembly import KnowledgeExportDisassemblyMixin
from .knowledge_export_fields import KnowledgeExportFieldsMixin
from .knowledge_export_methods import KnowledgeExportMethodsMixin
from .knowledge_export_output import KnowledgeExportOutputMixin
from .knowledge_export_serialization import KnowledgeExportSerializationMixin
from .source_hash import default_source_hash


class KnowledgeExporter(
    KnowledgeExportCoreMixin,
    KnowledgeExportFieldsMixin,
    KnowledgeExportMethodsMixin,
    KnowledgeExportDisassemblyMixin,
    KnowledgeExportOutputMixin,
    KnowledgeExportSerializationMixin,
):
    """Compatibility façade for graph export stages."""

    SCHEMA_VERSION = "1.0"
    PRODUCER = "ddon-dwarf-reconstructor"

    def __init__(
        self,
        elf_path: Path,
        build_id: str,
        requires_resolution: Callable[[int], bool] | None = None,
        source_hash: SourceHashPort | None = None,
    ) -> None:
        """Initialize an exporter.

        Args:
            elf_path: ELF file from which the DWARF information was read.
            build_id: Stable identifier for the client build represented by the ELF.
            requires_resolution: Optional callback used to decide whether a
                referenced type offset should be treated as a required structural
                dependency.
        """
        self.elf_path = elf_path
        self.build_id = build_id
        self.requires_resolution = requires_resolution
        self.source_hash = source_hash or default_source_hash()

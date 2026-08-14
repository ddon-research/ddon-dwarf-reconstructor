"""Knowledge-export operations for the application generator."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ...core.observability import get_logger
from ...domain.models.tool_evidence import ToolExport
from ...domain.ports.dwarf_lookup import DwarfLookupPort
from ...domain.services.parsing.die_type_classifier import DIETypeClassifier
from ..generation.runtime import GenerationRuntime
from .dwarf_header_generation import HeaderGenerationService

logger = get_logger(__name__)


class KnowledgeExportService:
    @staticmethod
    def export_knowledge_graph(
        context: GenerationRuntime,
        root_symbol: str,
        output_dir: Path,
        build_id: str,
        *,
        orbis_objdump_path: Path | None = None,
        tool_exports: Sequence[ToolExport] = (),
    ) -> Path:
        """Export a deterministic DWARF closure and optional Orbis evidence.

        Args:
            root_symbol: Root type whose hierarchy and dependencies are exported.
            output_dir: Directory receiving the knowledge bundle.
            build_id: Stable identifier for the input build.
            orbis_objdump_path: Optional pinned Orbis objdump executable.
            tool_exports: Complete source-bound exports from explicit tool profiles.

        Returns:
            Path to the generated manifest.
        """
        from ...application.exporters.knowledge_exporter import KnowledgeExporter

        HeaderGenerationService._expand_typedef_search(context, full_hierarchy=True)
        # Knowledge export keeps method declarations but uses structural closure
        # so signature-only types cannot trigger an unbounded cold CU search.
        class_infos, hierarchy_order = HeaderGenerationService._build_hierarchy_with_timing(
            context,
            root_symbol,
            include_method_signatures=False,
        )
        if not HeaderGenerationService._validate_hierarchy(context, class_infos, root_symbol):
            raise ValueError(f"No classes found in hierarchy for {root_symbol}")

        all_typedefs = HeaderGenerationService._collect_typedefs_and_packing(context, class_infos)
        reconstructed_cpp = context.header_renderer.generate_single_file_hierarchy_header(
            class_infos,
            hierarchy_order,
            root_symbol,
            typedefs=all_typedefs,
        )

        disassembly_report = None
        if orbis_objdump_path is not None:
            if context.disassembly_factory is None:
                raise RuntimeError("No disassembly producer configured")
            disassembly_report = context.disassembly_factory(orbis_objdump_path).produce(
                context.elf_path, root_symbol
            )

        if context.source_hash is None:
            raise RuntimeError("Knowledge export requires a source identity service")
        exporter = KnowledgeExporter(
            context.elf_path,
            build_id,
            source_hash=context.source_hash,
            requires_resolution=lambda offset: KnowledgeExportService._requires_resolution(
                context.lazy_index, offset
            ),
        )
        return exporter.export(
            root_symbol,
            class_infos,
            hierarchy_order,
            output_dir,
            reconstructed_cpp=reconstructed_cpp,
            disassembly_report=disassembly_report,
            tool_exports=tool_exports,
        )

    @staticmethod
    def _requires_resolution(index: DwarfLookupPort | None, offset: int) -> bool:
        """Require graph closure only for concrete, non-transparent aggregate DIEs."""
        if index is None:
            return True
        die = index.get_die_by_offset(offset)
        if die is None:
            return True
        return DIETypeClassifier.requires_resolution(die)

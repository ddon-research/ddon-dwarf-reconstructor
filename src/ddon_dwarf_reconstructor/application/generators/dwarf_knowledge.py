"""Focused operations extracted from the public compatibility façade."""

from __future__ import annotations

from pathlib import Path

from ...core.observability import get_logger
from .dwarf_generator_context import DwarfGeneratorContext

logger = get_logger(__name__)


class KnowledgeExportMixin:
    def export_knowledge_graph(
        self: DwarfGeneratorContext,
        root_symbol: str,
        output_dir: Path,
        build_id: str,
        *,
        orbis_objdump_path: Path | None = None,
    ) -> Path:
        """Export a deterministic DWARF closure and optional Orbis evidence.

        Args:
            root_symbol: Root type whose hierarchy and dependencies are exported.
            output_dir: Directory receiving the knowledge bundle.
            build_id: Stable identifier for the input build.
            orbis_objdump_path: Optional pinned Orbis objdump executable.

        Returns:
            Path to the generated manifest.
        """
        from ...application.exporters.knowledge_exporter import KnowledgeExporter

        self._expand_typedef_search(full_hierarchy=True)
        # Knowledge export keeps method declarations but uses structural closure
        # so signature-only types cannot trigger an unbounded cold CU search.
        class_infos, hierarchy_order = self._build_hierarchy_with_timing(
            root_symbol,
            include_method_signatures=False,
        )
        if not self._validate_hierarchy(class_infos, root_symbol):
            raise ValueError(f"No classes found in hierarchy for {root_symbol}")

        all_typedefs = self._collect_typedefs_and_packing(class_infos)
        assert self.header_generator is not None
        reconstructed_cpp = self.header_generator.generate_single_file_hierarchy_header(
            class_infos,
            hierarchy_order,
            root_symbol,
            typedefs=all_typedefs,
        )

        disassembly_report = None
        if orbis_objdump_path is not None:
            if self.disassembly_factory is None:
                raise RuntimeError("No disassembly producer configured")
            disassembly_report = self.disassembly_factory(orbis_objdump_path).produce(
                self.elf_path, root_symbol
            )

        exporter_options = {}
        source_hash = getattr(self, "source_hash", None)
        if source_hash is not None:
            exporter_options["source_hash"] = source_hash
        exporter = KnowledgeExporter(self.elf_path, build_id, **exporter_options)
        return exporter.export(
            root_symbol,
            class_infos,
            hierarchy_order,
            output_dir,
            reconstructed_cpp=reconstructed_cpp,
            disassembly_report=disassembly_report,
        )

"""Typed application facade for generation and knowledge-export use cases."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ...domain.models.tool_evidence import ToolExport
from ..generators.dwarf_header_generation import HeaderGenerationService
from ..generators.dwarf_knowledge import KnowledgeExportService
from ..generators.dwarf_multi_file import MultiFileGenerationService
from ..generators.generation_contracts import GenerationRequest, HeaderBundle
from .runtime import GenerationRuntime


@dataclass(frozen=True, slots=True)
class GenerationFacade:
    """Coordinate one ready component graph through use-case operations.

    The facade deliberately exposes workflow-level operations only.  Renderer
    and hierarchy helpers remain implementation details of the application
    services instead of becoming a second, forwarding-only public API.
    """

    _runtime: GenerationRuntime

    def generate(self, request: GenerationRequest) -> HeaderBundle:
        """Execute one typed header-generation request."""
        if request.full_hierarchy and not request.single_file:
            headers = MultiFileGenerationService.generate_multi_file_hierarchy(
                self._runtime,
                request.symbol,
                include_metadata=request.include_metadata,
            )
            return HeaderBundle(headers)
        if request.full_hierarchy:
            content = HeaderGenerationService.generate_complete_hierarchy_header(
                self._runtime,
                request.symbol,
                include_metadata=request.include_metadata,
            )
        else:
            content = HeaderGenerationService.generate_header(
                self._runtime,
                request.symbol,
                include_metadata=request.include_metadata,
            )
        return HeaderBundle.single(request.symbol, content)

    def export_knowledge_graph(
        self,
        root_symbol: str,
        output_dir: Path,
        build_id: str,
        *,
        orbis_objdump_path: Path | None = None,
        tool_exports: Sequence[ToolExport] = (),
    ) -> Path:
        return KnowledgeExportService.export_knowledge_graph(
            self._runtime,
            root_symbol,
            output_dir,
            build_id,
            orbis_objdump_path=orbis_objdump_path,
            tool_exports=tool_exports,
        )

"""Orbis disassembly projection for the knowledge-export façade."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from ...domain.models.disassembly import OrbisDisassemblyReport, OrbisFunctionDisassembly
from .knowledge_export_context import KnowledgeExportContext


class KnowledgeExportDisassemblyMixin:
    def _disassembly_records(
        self: KnowledgeExportContext,
        root_symbol: str,
        report: OrbisDisassemblyReport,
        elf_source_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        """Project Orbis ranges into graph records and structured instructions."""
        tool_id = f"source:tool:orbis-objdump:{report.tool.executable_sha256[:16]}"
        nodes = [self._tool_node(tool_id, report)]
        relationships: list[dict[str, Any]] = []
        instructions: list[dict[str, Any]] = []
        selected_addresses = {function.symbol.address for function in report.functions}
        emitted_targets: set[int] = set()
        for function in report.functions:
            function_nodes, function_relationships, function_instructions = self._function_records(
                root_symbol,
                report,
                function,
                tool_id,
                elf_source_id,
                selected_addresses,
                emitted_targets,
            )
            nodes.extend(function_nodes)
            relationships.extend(function_relationships)
            instructions.extend(function_instructions)
        tool_source = {
            "id": tool_id,
            "path": "orbis-objdump",
            "sha256": report.tool.executable_sha256,
            "format": "executable",
            "version": report.tool.version,
            "target": report.tool.target,
        }
        return nodes, relationships, instructions, tool_source

    def _tool_node(
        self: KnowledgeExportContext, tool_id: str, report: OrbisDisassemblyReport
    ) -> dict[str, Any]:
        return self._node(
            tool_id,
            "SourceArtifact",
            {
                "path": "orbis-objdump",
                "sha256": report.tool.executable_sha256,
                "format": "executable",
                "producer": "sce-orbis-sdk",
                "version": report.tool.version,
                "target": report.tool.target,
                "deterministic": True,
            },
        )

    def _function_records(
        self: KnowledgeExportContext,
        root_symbol: str,
        report: OrbisDisassemblyReport,
        function: OrbisFunctionDisassembly,
        tool_id: str,
        elf_source_id: str,
        selected_addresses: set[int],
        emitted_targets: set[int],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        symbol = function.symbol
        function_id = self._orbis_function_id(symbol.address)
        evidence_id = (
            f"evidence:{self.build_id}:orbis:{symbol.address:x}:{symbol.end_address:x}:"
            f"{report.artifact_key[:16]}"
        )
        unit_id = (
            f"disassembly:{self.build_id}:orbis:{symbol.address:x}:{symbol.size:x}:"
            f"{report.artifact_key[:16]}"
        )
        nodes = self._function_nodes(root_symbol, report, function, evidence_id, unit_id)
        relationships = self._function_relationships(
            root_symbol, function_id, unit_id, evidence_id, elf_source_id, tool_id
        )
        instructions, call_nodes, call_relationships = self._instruction_records(
            function,
            function_id,
            evidence_id,
            selected_addresses,
            emitted_targets,
        )
        nodes.extend(call_nodes)
        relationships.extend(call_relationships)
        return nodes, relationships, instructions

    def _function_nodes(
        self: KnowledgeExportContext,
        root_symbol: str,
        report: OrbisDisassemblyReport,
        function: OrbisFunctionDisassembly,
        evidence_id: str,
        unit_id: str,
    ) -> list[dict[str, Any]]:
        symbol = function.symbol
        direct_call_count, indirect_call_count, source_locations = self._function_metrics(function)
        return [
            self._orbis_function_node(symbol.address, symbol.name, symbol.size),
            self._node(
                evidence_id,
                "Evidence",
                {
                    "evidence_kind": "instruction_range",
                    "producer": "sce-orbis-sdk.orbis-objdump",
                    "source_revision": self.build_id,
                    "address_start": symbol.address,
                    "address_end": symbol.end_address,
                    "instruction_count": len(function.instructions),
                    "direct_call_count": direct_call_count,
                    "indirect_call_count": indirect_call_count,
                    "source_locations": source_locations,
                    "artifact_key": report.artifact_key,
                    "deterministic": True,
                },
            ),
            self._node(
                unit_id,
                "DisassemblyUnit",
                {
                    "name": symbol.name,
                    "owner_name": root_symbol,
                    "producer": "sce-orbis-sdk.orbis-objdump",
                    "source_revision": self.build_id,
                    "address_start": symbol.address,
                    "address_end": symbol.end_address,
                    "byte_size": symbol.size,
                    "instruction_count": len(function.instructions),
                    "completeness": "complete" if function.instructions else "not_observed",
                    "diagnostics": [] if function.instructions else ["NO_DECODED_INSTRUCTIONS"],
                    "artifact_key": report.artifact_key,
                    "deterministic": True,
                },
            ),
        ]

    @staticmethod
    def _function_metrics(function: OrbisFunctionDisassembly) -> tuple[int, int, list[str]]:
        direct_calls = [
            instruction
            for instruction in function.instructions
            if instruction.call_target_address is not None
        ]
        indirect_calls = sum(
            1
            for instruction in function.instructions
            if instruction.mnemonic.startswith("call") and instruction.call_target_address is None
        )
        source_locations = sorted(
            {
                f"{instruction.source_file}:{instruction.source_line}"
                for instruction in function.instructions
                if instruction.source_file is not None and instruction.source_line is not None
            }
        )
        return len(direct_calls), indirect_calls, source_locations

    def _function_relationships(
        self: KnowledgeExportContext,
        root_symbol: str,
        function_id: str,
        unit_id: str,
        evidence_id: str,
        elf_source_id: str,
        tool_id: str,
    ) -> list[dict[str, Any]]:
        logical_type_id = f"logical-type:{root_symbol}"
        return [
            self._relationship(function_id, "USES_TYPE", logical_type_id),
            self._relationship(function_id, "EVIDENCED_BY", evidence_id),
            self._relationship(unit_id, "ABOUT", logical_type_id),
            self._relationship(unit_id, "COVERS_FUNCTION", function_id),
            self._relationship(unit_id, "EVIDENCED_BY", evidence_id),
            self._relationship(evidence_id, "DERIVED_FROM", elf_source_id),
            self._relationship(evidence_id, "DERIVED_FROM", tool_id),
        ]

    def _instruction_records(
        self: KnowledgeExportContext,
        function: OrbisFunctionDisassembly,
        function_id: str,
        evidence_id: str,
        selected_addresses: set[int],
        emitted_targets: set[int],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        instructions: list[dict[str, Any]] = []
        nodes: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        for instruction in function.instructions:
            instructions.append({"function_id": function_id, **asdict(instruction)})
            target_address = instruction.call_target_address
            if target_address is None:
                continue
            target_id = self._orbis_function_id(target_address)
            if target_address not in selected_addresses and target_address not in emitted_targets:
                nodes.append(
                    self._orbis_function_node(
                        target_address,
                        instruction.call_target_name or f"sub_{target_address:x}",
                        None,
                    )
                )
                emitted_targets.add(target_address)
            relationships.append(
                self._relationship(
                    function_id,
                    "CALLS",
                    target_id,
                    {
                        "producer": "sce-orbis-sdk.orbis-objdump",
                        "instruction_address": instruction.address,
                        "evidence_id": evidence_id,
                        "direct": True,
                    },
                )
            )
        return instructions, nodes, relationships

    def _orbis_function_id(self: KnowledgeExportContext, address: int) -> str:
        return f"function:{self.build_id}:orbis:{address:x}"

    def _orbis_function_node(
        self: KnowledgeExportContext, address: int, name: str, size: int | None
    ) -> dict[str, Any]:
        qualified_name = re.sub(r"^(?:non-virtual|virtual) thunk to ", "", name)
        qualified_name = re.sub(r"\+0x[0-9a-fA-F]+$", "", qualified_name)
        return self._node(
            self._orbis_function_id(address),
            "Function",
            {
                "qualified_name": qualified_name,
                "signature": qualified_name,
                "name": qualified_name.rsplit("::", 1)[-1].split("(", 1)[0],
                "address": address,
                "byte_size": size,
                "producer": "sce-orbis-sdk.orbis-objdump",
                "source_revision": self.build_id,
                "deterministic": True,
            },
        )

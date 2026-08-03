"""Canonical reconstructor and deterministic fixture workload builders."""

from __future__ import annotations

import sys
from pathlib import Path

from ...domain.models.performance import ColdWarmState, PerformanceWorkload, RuntimeDescriptor


def build_reconstructor_workload(
    *,
    repository_root: Path,
    name: str,
    elf: Path,
    symbols: tuple[str, ...],
    mode: str,
    state: ColdWarmState,
    output_dir: Path,
    dwarf_dump: Path | None = None,
    dwarf_index: Path | None = None,
    build_id: str | None = None,
    orbis_objdump: Path | None = None,
    symbols_file: Path | None = None,
    full_hierarchy: bool = False,
    single_file: bool = False,
    exhaustive: bool = False,
    resolve_param_names: bool = False,
    timeout_seconds: float = 300.0,
    python_executable: Path | None = None,
    launcher: Path | None = None,
    runtime: RuntimeDescriptor | None = None,
) -> PerformanceWorkload:
    """Build a workload that invokes the canonical Typer command tree."""
    if mode not in {"generate", "export-knowledge"}:
        raise ValueError("performance mode must be generate or export-knowledge")
    if not symbols and symbols_file is None:
        raise ValueError("performance workload requires a symbol or symbols file")
    arguments = [*_command_prefix(python_executable, launcher), mode, str(elf)]
    arguments.extend(_symbol_arguments(symbols, symbols_file))
    _append_mode_arguments(
        arguments, mode, output_dir, build_id, orbis_objdump, full_hierarchy, single_file
    )
    _append_common_arguments(arguments, dwarf_dump, dwarf_index, exhaustive, resolve_param_names)
    configuration = (
        ("build_id", build_id or ""),
        ("dwarf_dump", str(dwarf_dump or "")),
        ("dwarf_index", str(dwarf_index or "")),
        ("mode", mode),
        ("orbis_objdump", str(orbis_objdump or "")),
        ("symbols", ",".join(symbols)),
    )
    return PerformanceWorkload(
        name=name,
        command=tuple(arguments),
        cwd=repository_root,
        state=state,
        timeout_seconds=timeout_seconds,
        source_path=elf,
        configuration=configuration,
        runtime=runtime,
    )


def _symbol_arguments(symbols: tuple[str, ...], symbols_file: Path | None) -> list[str]:
    arguments = [item for symbol in symbols for item in ("--symbol", symbol)]
    if symbols_file is not None:
        arguments.extend(("--symbols-file", str(symbols_file)))
    return arguments


def _append_mode_arguments(
    arguments: list[str],
    mode: str,
    output_dir: Path,
    build_id: str | None,
    orbis_objdump: Path | None,
    full_hierarchy: bool,
    single_file: bool,
) -> None:
    if mode == "export-knowledge":
        arguments.extend(("--output-dir", str(output_dir)))
        if build_id:
            arguments.extend(("--build-id", build_id))
        if orbis_objdump:
            arguments.extend(("--orbis-objdump", str(orbis_objdump)))
        return
    arguments.extend(("--output", str(output_dir)))
    if full_hierarchy:
        arguments.append("--full-hierarchy")
    if single_file:
        arguments.append("--single-file")


def _append_common_arguments(
    arguments: list[str],
    dwarf_dump: Path | None,
    dwarf_index: Path | None,
    exhaustive: bool,
    resolve_param_names: bool,
) -> None:
    optional_paths = (("--dwarf-dump", dwarf_dump), ("--dwarf-index", dwarf_index))
    for option, path in optional_paths:
        if path is not None:
            arguments.extend((option, str(path)))
    if exhaustive:
        arguments.append("--exhaustive")
    if resolve_param_names:
        arguments.append("--resolve-param-names")


def build_fixture_workload(
    *,
    repository_root: Path,
    name: str,
    state: ColdWarmState,
    timeout_seconds: float,
    python_executable: Path | None = None,
    launcher: Path | None = None,
    runtime: RuntimeDescriptor | None = None,
) -> PerformanceWorkload:
    """Build a small deterministic workload for gated resource regression tests."""
    return PerformanceWorkload(
        name=name,
        command=(
            *_command_prefix(
                python_executable,
                launcher,
                module="ddon_dwarf_reconstructor.infrastructure.performance.fixture_target",
            ),
        ),
        cwd=repository_root,
        state=state,
        timeout_seconds=timeout_seconds,
        configuration=(("fixture", "deterministic-v1"),),
        runtime=runtime,
    )


def build_dump_index_workload(
    *,
    repository_root: Path,
    name: str,
    dwarf_dump: Path,
    index_path: Path | None,
    state: ColdWarmState,
    timeout_seconds: float,
    runtime: RuntimeDescriptor | None = None,
) -> PerformanceWorkload:
    """Build a workload for one explicit streaming compressed-dump index rebuild."""
    command = [
        *_command_prefix(python_executable=None, launcher=None),
        "artifacts",
        "rebuild-dump-index",
        str(dwarf_dump),
    ]
    if index_path is not None:
        command.extend(("--index-path", str(index_path)))
    configuration = (
        ("dwarf_dump", str(dwarf_dump)),
        ("dwarf_index", str(index_path or "")),
        ("mode", "artifacts-rebuild-dump-index"),
    )
    return PerformanceWorkload(
        name=name,
        command=tuple(command),
        cwd=repository_root,
        state=state,
        timeout_seconds=timeout_seconds,
        source_path=dwarf_dump,
        configuration=configuration,
        runtime=runtime,
    )


def _command_prefix(
    python_executable: Path | None,
    launcher: Path | None,
    *,
    module: str | None = None,
) -> list[str]:
    if python_executable is not None and launcher is not None:
        raise ValueError("choose either a Python executable or a compiled launcher")
    if launcher is not None:
        return [str(launcher)]
    return [str(python_executable or sys.executable), "-m", module or "ddon_dwarf_reconstructor"]


__all__ = [
    "build_dump_index_workload",
    "build_fixture_workload",
    "build_reconstructor_workload",
]

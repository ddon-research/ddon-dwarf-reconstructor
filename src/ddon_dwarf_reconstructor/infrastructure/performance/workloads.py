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
    dwarf_store_manifest: Path | None = None,
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
    query_trace_path: Path | None = None,
    query_trace_profile_threshold_ms: float = 500.0,
    query_trace_max_profiles: int = 20,
) -> PerformanceWorkload:
    """Build a workload that invokes the canonical Typer command tree."""
    _validate_reconstructor_workload(
        mode,
        symbols,
        symbols_file,
        query_trace_profile_threshold_ms,
        query_trace_max_profiles,
    )
    command, configuration, environment = _reconstructor_parts(
        python_executable,
        launcher,
        mode,
        elf,
        symbols,
        symbols_file,
        output_dir,
        build_id,
        orbis_objdump,
        full_hierarchy,
        single_file,
        dwarf_dump,
        dwarf_index,
        dwarf_store_manifest,
        exhaustive,
        resolve_param_names,
        query_trace_path,
        query_trace_profile_threshold_ms,
        query_trace_max_profiles,
    )
    return PerformanceWorkload(
        name=name,
        command=tuple(command),
        cwd=repository_root,
        state=state,
        timeout_seconds=timeout_seconds,
        source_path=elf,
        configuration=configuration,
        environment=tuple(environment),
        runtime=runtime,
    )


def _reconstructor_parts(
    python_executable: Path | None,
    launcher: Path | None,
    mode: str,
    elf: Path,
    symbols: tuple[str, ...],
    symbols_file: Path | None,
    output_dir: Path,
    build_id: str | None,
    orbis_objdump: Path | None,
    full_hierarchy: bool,
    single_file: bool,
    dwarf_dump: Path | None,
    dwarf_index: Path | None,
    dwarf_store_manifest: Path | None,
    exhaustive: bool,
    resolve_param_names: bool,
    query_trace_path: Path | None,
    query_trace_profile_threshold_ms: float,
    query_trace_max_profiles: int,
) -> tuple[list[str], tuple[tuple[str, str], ...], list[tuple[str, str]]]:
    command = _reconstructor_arguments(
        python_executable,
        launcher,
        mode,
        elf,
        symbols,
        symbols_file,
        output_dir,
        build_id,
        orbis_objdump,
        full_hierarchy,
        single_file,
        dwarf_dump,
        dwarf_index,
        dwarf_store_manifest,
        exhaustive,
        resolve_param_names,
    )
    configuration = _reconstructor_configuration(
        build_id,
        dwarf_dump,
        dwarf_index,
        dwarf_store_manifest,
        mode,
        orbis_objdump,
        symbols,
        query_trace_path,
        query_trace_profile_threshold_ms,
        query_trace_max_profiles,
    )
    environment = _reconstructor_environment(
        query_trace_path,
        query_trace_profile_threshold_ms,
        query_trace_max_profiles,
    )
    return command, configuration, environment


def _validate_reconstructor_workload(
    mode: str,
    symbols: tuple[str, ...],
    symbols_file: Path | None,
    query_trace_profile_threshold_ms: float,
    query_trace_max_profiles: int,
) -> None:
    if mode not in {"generate", "export-knowledge"}:
        raise ValueError("performance mode must be generate or export-knowledge")
    if not symbols and symbols_file is None:
        raise ValueError("performance workload requires a symbol or symbols file")
    if query_trace_profile_threshold_ms <= 0:
        raise ValueError("query_trace_profile_threshold_ms must be positive")
    if query_trace_max_profiles < 1:
        raise ValueError("query_trace_max_profiles must be positive")


def _reconstructor_arguments(
    python_executable: Path | None,
    launcher: Path | None,
    mode: str,
    elf: Path,
    symbols: tuple[str, ...],
    symbols_file: Path | None,
    output_dir: Path,
    build_id: str | None,
    orbis_objdump: Path | None,
    full_hierarchy: bool,
    single_file: bool,
    dwarf_dump: Path | None,
    dwarf_index: Path | None,
    dwarf_store_manifest: Path | None,
    exhaustive: bool,
    resolve_param_names: bool,
) -> list[str]:
    arguments = [*_command_prefix(python_executable, launcher), mode, str(elf)]
    arguments.extend(_symbol_arguments(symbols, symbols_file))
    _append_mode_arguments(
        arguments, mode, output_dir, build_id, orbis_objdump, full_hierarchy, single_file
    )
    _append_common_arguments(
        arguments,
        dwarf_dump,
        dwarf_index,
        dwarf_store_manifest,
        exhaustive,
        resolve_param_names,
    )
    return arguments


def _reconstructor_configuration(
    build_id: str | None,
    dwarf_dump: Path | None,
    dwarf_index: Path | None,
    dwarf_store_manifest: Path | None,
    mode: str,
    orbis_objdump: Path | None,
    symbols: tuple[str, ...],
    query_trace_path: Path | None,
    query_trace_profile_threshold_ms: float,
    query_trace_max_profiles: int,
) -> tuple[tuple[str, str], ...]:
    return (
        ("build_id", build_id or ""),
        ("dwarf_dump", str(dwarf_dump or "")),
        ("dwarf_index", str(dwarf_index or "")),
        ("dwarf_store", str(dwarf_store_manifest or "")),
        ("mode", mode),
        ("orbis_objdump", str(orbis_objdump or "")),
        ("symbols", ",".join(symbols)),
        ("query_trace_path", str(query_trace_path or "")),
        ("query_trace_profile_threshold_ms", str(query_trace_profile_threshold_ms)),
        ("query_trace_max_profiles", str(query_trace_max_profiles)),
    )


def _reconstructor_environment(
    query_trace_path: Path | None,
    query_trace_profile_threshold_ms: float,
    query_trace_max_profiles: int,
) -> list[tuple[str, str]]:
    environment = [("PYTHONFAULTHANDLER", "1")]
    if query_trace_path is not None:
        environment.extend(
            (
                ("DDON_DORIS_QUERY_TRACE_PATH", str(query_trace_path.resolve())),
                (
                    "DDON_DORIS_QUERY_TRACE_PROFILE_THRESHOLD_MS",
                    str(query_trace_profile_threshold_ms),
                ),
                ("DDON_DORIS_QUERY_TRACE_MAX_PROFILES", str(query_trace_max_profiles)),
            )
        )
    return environment


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
    dwarf_store_manifest: Path | None,
    exhaustive: bool,
    resolve_param_names: bool,
) -> None:
    optional_paths = (
        ("--dwarf-dump", dwarf_dump),
        ("--dwarf-index", dwarf_index),
        ("--dwarf-store", dwarf_store_manifest),
    )
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


def build_materializer_workload(
    *,
    repository_root: Path,
    name: str,
    elf: Path,
    output_dir: Path,
    max_cus: int | None,
    max_open_writers: int,
    parquet_layout: str,
    rotate_writers_every_cus: int,
    checkpoint_every_cus: int | None = None,
    timeout_seconds: float = 1800.0,
    python_executable: Path | None = None,
    runtime: RuntimeDescriptor | None = None,
) -> PerformanceWorkload:
    """Build the canonical bounded analytical-materializer workload."""
    _validate_materializer_workload(
        max_cus, max_open_writers, parquet_layout, rotate_writers_every_cus
    )
    arguments = _materializer_command(
        python_executable,
        elf,
        output_dir,
        max_cus,
        max_open_writers,
        parquet_layout,
        rotate_writers_every_cus,
        checkpoint_every_cus,
    )
    return PerformanceWorkload(
        name=name,
        command=tuple(arguments),
        cwd=repository_root,
        state=ColdWarmState.COLD,
        timeout_seconds=timeout_seconds,
        environment=(("PYTHONFAULTHANDLER", "1"),),
        source_path=elf,
        configuration=_materializer_configuration(
            max_cus,
            max_open_writers,
            parquet_layout,
            rotate_writers_every_cus,
            checkpoint_every_cus,
        ),
        runtime=runtime,
    )


def _validate_materializer_workload(
    max_cus: int | None,
    max_open_writers: int,
    parquet_layout: str,
    rotate_writers_every_cus: int,
) -> None:
    if max_cus is not None and max_cus < 1:
        raise ValueError("max_cus must be positive when provided")
    if max_open_writers < 1:
        raise ValueError("max_open_writers must be positive")
    if rotate_writers_every_cus < 0:
        raise ValueError("rotate_writers_every_cus must not be negative")
    if parquet_layout not in {"family", "bucketed"}:
        raise ValueError("parquet_layout must be family or bucketed")


def _materializer_command(
    python_executable: Path | None,
    elf: Path,
    output_dir: Path,
    max_cus: int | None,
    max_open_writers: int,
    parquet_layout: str,
    rotate_writers_every_cus: int,
    checkpoint_every_cus: int | None,
) -> list[str]:
    arguments = [
        *_command_prefix(python_executable, None),
        "artifacts",
        "materialize-dwarf",
        str(elf),
        "--output-dir",
        str(output_dir),
        "--write-parquet",
        "--no-write-jsonl",
        "--parquet-layout",
        parquet_layout,
        "--max-open-writers",
        str(max_open_writers),
        "--rotate-writers-every-cus",
        str(rotate_writers_every_cus),
    ]
    if max_cus is not None:
        arguments.extend(("--max-cus", str(max_cus)))
    if checkpoint_every_cus is not None:
        arguments.extend(("--checkpoint-every-cus", str(checkpoint_every_cus)))
    return arguments


def _materializer_configuration(
    max_cus: int | None,
    max_open_writers: int,
    parquet_layout: str,
    rotate_writers_every_cus: int,
    checkpoint_every_cus: int | None,
) -> tuple[tuple[str, str], ...]:
    return (
        ("max_cus", "" if max_cus is None else str(max_cus)),
        ("max_open_writers", str(max_open_writers)),
        ("parquet_layout", parquet_layout),
        ("rotate_writers_every_cus", str(rotate_writers_every_cus)),
        ("checkpoint_every_cus", "" if checkpoint_every_cus is None else str(checkpoint_every_cus)),
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
    "build_materializer_workload",
    "build_reconstructor_workload",
]

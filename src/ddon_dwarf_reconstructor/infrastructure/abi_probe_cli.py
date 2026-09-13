"""Typer command for publishing reusable compiler ABI probe evidence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer

from .artifact_cli_support import run_operation, write_result
from .implementation_abi_probes import (
    build_probe_manifest,
    run_abi_probe_matrix,
    write_probe_manifest,
)
from .orbis_toolchain_contracts import select_toolchain_profile

CompilerArgument = Annotated[Path, typer.Argument(help="Orbis clang++ compiler executable.")]
OutputOption = Annotated[
    Path,
    typer.Option("--output-dir", help="External directory for compiler ABI probe artifacts."),
]
ReadelfOption = Annotated[
    Path | None,
    typer.Option("--orbis-readelf", help="Optional matching Orbis readelf for object metadata."),
]
TimeoutOption = Annotated[
    float | None,
    typer.Option(
        "--timeout-seconds",
        min=0.001,
        help="Optional timeout for each compiler invocation.",
    ),
]


def probe_compiler_abi(
    compiler: CompilerArgument,
    output_dir: OutputOption,
    readelf: ReadelfOption = None,
    timeout_seconds: TimeoutOption = None,
) -> None:
    """Publish a reusable toolchain-bound compiler assembly/object probe matrix."""

    def operation() -> None:
        if not compiler.is_file():
            raise ValueError(f"Orbis compiler executable does not exist: {compiler}")
        profile, diagnostics = select_toolchain_profile(None, (compiler,))
        results = run_abi_probe_matrix(
            compiler,
            output_dir / "probes",
            readelf=readelf,
            timeout_seconds=timeout_seconds,
            toolchain_profile=profile,
        )
        manifest = build_probe_manifest(results, compiler, toolchain_profile=profile)
        if diagnostics:
            manifest = replace(manifest, diagnostics=(*manifest.diagnostics, *diagnostics))
        manifest_path = write_probe_manifest(
            manifest,
            output_dir / f"compiler-probes-{manifest.compiler_sha256[:16]}.json",
        )
        write_result({"manifest_path": str(manifest_path), "manifest": manifest.to_dict()})

    run_operation(operation)


__all__ = ["probe_compiler_abi"]

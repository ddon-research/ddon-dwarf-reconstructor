"""Typer option contracts for implementation validation."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

ElfArgument = Annotated[Path, typer.Argument(help="Source PS4 ELF to validate.")]
ReportOption = Annotated[
    Path,
    typer.Option(
        "--implementation-report", help="Source-bound implementation-discovery JSON report."
    ),
]
OutputOption = Annotated[
    Path,
    typer.Option(
        "--output-dir", help="External directory for validation reports and target objects."
    ),
]
LoadBaseOption = Annotated[
    str | None,
    typer.Option("--load-base", help="Explicit aligned runtime image base, for example 0x400000."),
]
OriginalAddressesOption = Annotated[
    bool,
    typer.Option(
        "--original-addresses",
        help="Use ELF virtual addresses as the explicit runtime address policy.",
    ),
]
DwarfStoreOption = Annotated[
    Path | None,
    typer.Option(
        "--dwarf-store",
        help="Complete source-bound analytical DWARF manifest for method ABI/CFI context.",
    ),
]
NidDatabaseOption = Annotated[
    Path | None,
    typer.Option(
        "--nid-database", help="Optional source-bound JSON or two-column NID-name database."
    ),
]
NidDatabaseProvenanceOption = Annotated[
    Path | None,
    typer.Option(
        "--nid-database-provenance",
        help="Optional JSON provenance manifest for the NID database.",
    ),
]
SdkRootOption = Annotated[
    Path | None,
    typer.Option("--sdk-root", help="PS4 SDK root used only to locate host acceptance tools."),
]
OrbisAsOption = Annotated[
    Path | None,
    typer.Option(
        "--orbis-as", help="Explicit Orbis assembler path; otherwise resolve from the SDK root."
    ),
]
OrbisClangOption = Annotated[
    Path | None,
    typer.Option("--orbis-clang", help="Explicit Orbis clang++ path for the ABI probe matrix."),
]
OrbisReadelfOption = Annotated[
    Path | None,
    typer.Option("--orbis-readelf", help="Explicit Orbis readelf path for target-object metadata."),
]
OrbisObjdumpOption = Annotated[
    Path | None,
    typer.Option(
        "--orbis-objdump",
        help="Explicit Orbis objdump path for generated-object CFG and call-edge parity.",
    ),
]
OrbisLdOption = Annotated[
    Path | None,
    typer.Option(
        "--orbis-ld", help="Optional Orbis linker path for a relocatable target-object result."
    ),
]
ToolTimeoutSecondsOption = Annotated[
    float | None,
    typer.Option(
        "--tool-timeout-seconds",
        min=0.001,
        help="Optional limit for each SDK tool invocation; unset means no limit.",
    ),
]
ToolEvidenceOption = Annotated[
    list[Path] | None,
    typer.Option(
        "--tool-evidence",
        help="Complete source-bound external-tool manifest; repeat for multiple profiles.",
    ),
]
AssemblyProfileOption = Annotated[
    str,
    typer.Option(
        "--assembly-profile",
        help="Assembly emission profile: byte-replay (default) or sectioned.",
    ),
]
AbiProbeManifestOption = Annotated[
    Path | None,
    typer.Option(
        "--abi-probe-manifest",
        help="Reusable toolchain-bound compiler ABI probe manifest.",
    ),
]

__all__ = [
    "AbiProbeManifestOption",
    "AssemblyProfileOption",
    "DwarfStoreOption",
    "ElfArgument",
    "LoadBaseOption",
    "NidDatabaseOption",
    "NidDatabaseProvenanceOption",
    "OrbisAsOption",
    "OrbisClangOption",
    "OrbisLdOption",
    "OrbisObjdumpOption",
    "OrbisReadelfOption",
    "OriginalAddressesOption",
    "OutputOption",
    "ReportOption",
    "SdkRootOption",
    "ToolEvidenceOption",
    "ToolTimeoutSecondsOption",
]

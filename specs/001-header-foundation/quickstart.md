# Quickstart: Header Foundation Validation

## Prerequisites

- Regular CPython 3.14.6.
- `uv sync --python 3.14.6 --extra dev` completed.
- Repository root as the working directory.
- For real validation only: explicit local paths to the PS4 ELF, compressed DWARF
  dump, SQLite sidecar, and optional Orbis objdump.
- For compiler validation: Visual Studio Community 2026 with the x64 VC tools
  component, discovered through `C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe`.

## Focused Unit Checks

Run the implemented baseline slices:

```powershell
uv run pytest tests/generators/test_dwarf_generator.py
uv run pytest tests/domain/services/test_lazy_dwarf_index_service.py
uv run pytest tests/infrastructure/test_zstd_dump_parser.py
uv run pytest tests/test_artifact_cli.py
```

Expected outcomes:

- generator construction and dump discovery pass;
- source-bound lazy-index tests pass;
- compressed dump indexing uses one streaming pass and warm lookups do not reopen the
  dump;
- source changes rebuild the sidecar while timestamp-only changes reuse it;
- artifact inspect, repair, and exact-path purge behavior pass.

## Quality Checks

```powershell
uvx ruff@0.16.1 check --no-fix src tests
uvx ruff@0.16.1 format --check src tests
uv run mypy src
```

Existing unrelated diagnostics must be resolved or explicitly recorded before the
feature is considered complete. Do not weaken strictness to hide failures.

## Real PS4 Checks

Use explicit local paths and preserve the durable sidecar:

```powershell
$env:DDON_REAL_ELF = 'D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf'
$env:DDON_REAL_DWARF_DUMP = "$env:DDON_REAL_ELF.llvmdwarfdump.zst"
$env:DDON_REAL_DWARF_INDEX = 'D:\ddon-dwarf-reconstructor\output\real-dump-index\DDOORBIS.elf.llvmdwarfdump.index.sqlite3'
uv run ddon-dwarf-artifacts inspect --elf $env:DDON_REAL_ELF `
  --dwarf-dump $env:DDON_REAL_DWARF_DUMP `
  --dump-index $env:DDON_REAL_DWARF_INDEX
```

Real tests remain opt-in and must not delete or rebuild a validated index without an
explicit operation. Compare generated headers, manifests, and diagnostics byte-for-
byte across fresh processes.

## MSVC Sample Verification

The current validation corpus is:

- Random resource candidates: `rTextureMemory`, `rTexture`,
  `rTutorialDialogMessage`.
- IDA anchors: `cSetInfoOmBreakTarget`, `rLayout`.

The generated bundle is local and ignored:
`output/msvc-header-validation-20260801/`.

Load the x64 developer environment and run the prepared wrapper from the validation
directory:

```powershell
cmd.exe /d /c 'D:\ddon-dwarf-reconstructor\output\msvc-header-validation-20260801\compile_msvc.cmd'
```

Record one result for every standalone translation unit and one separate result for
the aggregate translation unit. Each result must include compiler version, complete
flags, exit code, captured stdout/stderr, object status, generated files, missing
framework dependencies, and whether each failure is a rendering defect, duplicate
declaration, or intentionally unresolved closure type. Include an explicit row for
`compile_tutorial.cpp` and classify C4201 warnings rather than silently ignoring them.

Compare the two anchors with
`resources/sample-ida-dump-cSetInfoOmBreakTarget.h` and
`resources/sample-ida-dump-rLayout.h`; classify recoverable fact matches separately
from IDA presentation details. If compiler stderr is unavailable, record a duplicate
declaration explanation as a hypothesis only; do not claim a confirmed C2011 error.

## Acceptance Checklist

- [x] Each of the five representative standalone generated headers compiles with the
  selected host compiler.
- [ ] The aggregate multi-header translation unit compiles with the selected host
  compiler and has a separately captured exit code and diagnostics.
- [ ] Layout and provenance assertions match the selected DWARF fixtures.
- [ ] Fresh-process warm results are byte-identical.
- [ ] Same-path source replacement invalidates stale artifacts.
- [ ] Assembly validation reports seeded disagreements with evidence identifiers.
- [x] Three random candidates and both IDA anchors have recorded generation,
  compilation, and comparison outcomes.
- [x] Simple `DW_OP_constu` virtual-table slots agree between DWARF and generated
  method evidence.

Current result: the five standalone headers compile with MSVC x64. The retained
standalone results are exit code 0 for `rTexture`, `rTextureMemory`,
`cSetInfoOmBreakTarget`, `rLayout`, and `rTutorialDialogMessage`; `rLayout` emits
two C4201 nameless-union warnings. The aggregate multi-header translation unit exits
with code 2, so the corpus is not an aggregate pass. Repeated shared declarations
are the current hypothesis from generated output, not a confirmed compiler error
because raw stderr was not retained. See
[verification-msvc-ida-20260801.md](verification-msvc-ida-20260801.md).

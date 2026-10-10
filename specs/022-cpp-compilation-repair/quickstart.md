# Validate a compilation repair slice

This guide is for contributors implementing Feature 022. It requires the locked development
environment, existing documentation validators, and explicit local source/store paths for the
real-asset tier. Commands describe validation to run during implementation; they do not imply
the current dirty producer passes. See [measured evidence](measured-evidence.md).

## Deterministic Slice

From the repository root, reproduce the alias failure before fixing it:

```powershell
uv run pytest tests/domain/services/generation/test_alias_rendering.py -q
uv run ruff check --no-fix src tests tools/sonar
uv run just test-unit
uv run just check
uv run just test
```

Use the exact focused tests named by the task for subsequent slices. Do not change expected
output merely to match the implementation. Refresh API pages with `uv run just docs-api` after
model/module changes; generated pages are not hand-edited. Before implementation handoff, run
`uv run just coverage-ci` and `uv run just audit` in addition to the complete fast gate.

## Real-Asset Preflight

Verify current service health, complete source-bound store identity, and bounded lookup status.
Use existing analytical artifact commands and deployment configuration; do not assume Gemini's
database/table names or repair storage simply because an old report contains an I/O error.
Freeze the effective producer and record toolchain/configuration identities before generation.

Inspect command surfaces before using them:

```powershell
uv run ddon-dwarf-reconstructor generate --help
uv run python tools/sonar/validate_header_bundle.py --help
```

The help was checked while authoring this guide. The validator requires named `--input-root`
and `--validation-directory` options; the proposal's positional-only invocation is invalid.

## Complete Root Request

Choose explicit verified paths for `$repairElf`, `$repairStore`, and a new `$repairOutput` in
the current shell. The first is the ELF file, the second its complete store manifest, and the
third a fresh external output directory. Do not reuse a baseline or probe directory.

```powershell
uv run ddon-dwarf-reconstructor generate $repairElf --symbols-file resources/season2-resources.txt --dwarf-store $repairStore --output $repairOutput --full-hierarchy
```

Context generation is enabled by default. Determine the actual version root from the published
manifest, assign it to `$repairVersionRoot`, and choose a separate new `$repairValidation` path:

```powershell
uv run python tools/sonar/validate_header_bundle.py --input-root $repairVersionRoot --validation-directory $repairValidation --timeout-seconds 3600
```

Inspect retained JSON for every header and aggregate result; process completion alone is not
acceptance. Reconcile all 289 roots and required declaration identities, not only file counts.
Run equivalent fresh/warm processes and separate `--no-generate-context` outputs, preserving
matching C++/assembly bytes and documenting intentional context-artifact differences. For
assembly-enabled profiles, retain the existing explicit tool/flag contract and compare like modes.

Use the existing Feature 021 performance workload matrix and canonical `performance` workflows.
Do not substitute new averages or traced timings for matching per-workload/cache-state p50/p95.
Record unresolved cases using the [handoff contract](contracts/acceptance.md).

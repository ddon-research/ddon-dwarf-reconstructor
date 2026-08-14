# Testing and evidence tiers

Root tests have exactly one scope marker (`unit`, `integration`, or `acceptance`) and at least one
purpose marker (`functional`, `regression`, or `non_functional`). Collection enforcement rejects
ambiguous or missing classifications. `performance`, `slow`, `real_asset`, `packaging`, and
`quality` are explicit qualifiers with additional constraints.

## Default selection

```powershell
uv run just test
uv run just coverage-ci
```

The default correctness expression includes deterministic integration and excludes performance,
packaging, and real-asset tests. `test-without-integration` is an iteration shortcut only. Use
the named recipes for regression, non-functional, acceptance, real-asset, and performance slices.

## What each tier proves

| Tier | Proves | Does not prove |
| --- | --- | --- |
| Unit | isolated parser, model, policy, or adapter behavior | full source integration |
| Deterministic integration | multiple project components and stable bundle contracts | proprietary tool behavior |
| Acceptance | user-visible CLI, packaging, or selected external workflow | every real corpus path |
| Real asset | explicitly named ELF/dump/compiler/tool result | fixture portability or repeatability without the asset |
| Performance | measured time/resource behavior with recorded cold/warm state | semantic correctness by itself |

The reusable performance workflow is documented in [Profile the application](../how-to/profile-performance.md)
and uses the canonical commands below:

```powershell
uv run just test-performance-fixtures
uv run just test-performance-real-assets
uv run just performance-profile-index
uv run just performance-runtime-compare
uv run just performance-history
uv run just analytical-fixture
uv run just analytical-compose-config
```

The fixture tier is deterministic and may enforce explicit budgets. Real-asset profiles are
environmental, report-only evidence. The tracked SQLite schema and generated static exports keep
history visible without committing raw profiles or proprietary inputs.

The knowledge exporter integration path must remain runnable without proprietary ELF inputs. Real
PS4/PS3 inputs are environmental evidence and are never silently substituted for deterministic
tests.

For the analytical store, use `uv run just analytical-materialize` and
`uv run just analytical-benchmark` only with an external output directory. The materializer writes
direct typed Parquet rows by default; add `--write-jsonl` only for a bounded audit fixture.
Full real-ELF materialization, LLVM verification, and Doris loading are separate acceptance
evidence. The local Docker daemon and the LLVM source checkout do not count as successful Doris or
`llvm-dwarfdump --verify` observations without an executable result.

For source-bound Season 2 generation, derive and report `root_count`, `bundle_count`,
`manifest_count`, `header_file_count`, `published_file_count`, and `msvc_unit_count` separately.
An output directory containing a manifest or a placeholder header is not evidence of a complete
root. `complete`, `partial`, `blocked`, and `not_observed` are evidence states; a passing repository
gate cannot replace unavailable Doris, MSVC, real-asset, or performance observations. A truncated
or unavailable query must remain non-complete through generation and must not publish a successful
placeholder bundle.

## Nested project

```powershell
uv run --directory tools/dwarf_spec_pipeline just test
uv run --directory tools/dwarf_spec_pipeline just test-official
uv run --directory tools/dwarf_spec_pipeline just check
```

The nested project mirrors the marker vocabulary but has its own lockfile and source boundary.

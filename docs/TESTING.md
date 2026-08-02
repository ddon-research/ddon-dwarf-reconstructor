# Testing and validation

The repository follows a practical test pyramid: many fast isolated tests, fewer deterministic
component integrations, and a small set of acceptance/environmental checks. Coverage is a risk
signal; it does not replace functional, regression, integration, or non-functional evidence.

## Required change loop

The default correctness loop includes deterministic integration tests. The explicit fast opt-out
exists for short iteration only and is not a merge-quality substitute.

```text
uv sync --python 3.14.6
uv run just test-unit
uv run just check
uv run just test
uv run just coverage-ci
uv run just audit
```

Useful selections:

```text
uv run just test-integration       # required deterministic integrations
uv run just test-without-integration  # exceptional fast opt-out
uv run just test-regression        # stable defect and output contracts
uv run just test-non-functional    # quality/operational checks except explicit resources
uv run just test-performance       # explicit benchmark tier
uv run just test-acceptance        # CLI, real-asset, and distribution acceptance
uv run just test-real-assets       # explicit local ELF/dump/compiler/artifact checks
uv run just package-smoke          # isolated uv tool installation
```

`test`, `coverage`, and `coverage-ci` select:

```text
-m "not performance and not packaging and not real_asset"
```

That expression includes unit tests and required local integration tests. It excludes the
performance benchmark, the packaging environment mutation, and tests that require a proprietary
or otherwise explicit local asset.

## Taxonomy

Every collected root test has exactly one execution scope. A collection hook in
`tests/conftest.py` rejects missing or ambiguous scopes and missing purposes under the existing
`--strict-markers` policy.

| Marker | Scope or purpose | Use it for |
| --- | --- | --- |
| `unit` | execution scope | One policy/service/adapter with controlled boundaries |
| `integration` | execution scope | Multiple real project components with deterministic local fixtures |
| `acceptance` | execution scope | User-visible CLI, distribution, or external-artifact flows |
| `functional` | purpose | Product behavior and output correctness |
| `regression` | purpose | A stable contract or previously observed failure; combine with functional when appropriate |
| `non_functional` | purpose | Performance, quality, maintainability, resource, or operational behavior |
| `performance` | qualifier | Time, throughput, or resource budget; must also be `non_functional` |
| `slow` | qualifier | Outside the normal fast feedback budget |
| `real_asset` | qualifier | Requires an explicit ELF, compressed dump, compiler, or generated artifact |
| `packaging` | qualifier | Installs and exercises the built distribution; must be `acceptance` |
| `quality` | qualifier | Architecture, structure, coverage, or repository-tooling policy; must be `non_functional` |

Ordinary scoped tests without a more specific purpose receive `functional` at collection time.
Tests in quality, performance, and real-asset modules declare `non_functional` explicitly. The
taxonomy audit is itself a non-functional quality test.

Examples:

```python
pytestmark = [pytest.mark.integration, pytest.mark.functional, pytest.mark.regression]


pytestmark = [
    pytest.mark.integration,
    pytest.mark.non_functional,
    pytest.mark.performance,
    pytest.mark.real_asset,
    pytest.mark.slow,
]
```

## Pyramid and current inventory

The 2026-08-03 root collection baseline is 433 tests:

| Layer/purpose | Current evidence |
| --- | ---: |
| Unit scope | 427 |
| Deterministic integration scope | 2 required exporter tests |
| Acceptance scope | 2 real-asset generation tests and 1 packaging test |
| Performance | 1 explicit real-asset budget |
| Regression purpose | 8 output/authority/acceptance contracts |
| Non-functional purpose | 28 quality/performance tests |

The unit layer remains the largest. The required integration layer is deliberately small and
crosses real application, source-identity, model, serialization, and filesystem boundaries in
`tests/application/exporters/test_knowledge_exporter_integration.py`. It does not depend on the
800 MB checkout ELF or the 30+ GB expanded DWARF dump.

Real generator tests in `tests/application/generators/test_dwarf_integration.py` are acceptance
tests qualified by `real_asset` and `slow`. They remain valuable evidence, but missing external
inputs must not remove the deterministic integration signal from the normal loop.

## Test structure

```text
tests/
├── application/       use-case, exporter, and generator tests
├── config/             configuration tests
├── domain/             model, parser, cache, and rendering tests
├── infrastructure/     ELF, dump, filesystem, logging, and adapter tests
├── performance/        explicit benchmark and real-asset budgets
├── packaging/          isolated distribution acceptance
├── quality/             architecture, structure, coverage, manifest, taxonomy gates
├── support/             typed fixtures, DIE builders, and quality helpers
├── tools/sonar/         local compiler-analysis tooling tests
└── conftest.py         fixtures and collection-time taxonomy enforcement
```

Keep tests beside the owning production boundary. Use `tests/support/` for typed fixtures rather
than duplicating fake DWARF graphs. Keep real inputs, caches, generated headers, and logs outside
source control.

## Regression and output evidence

Generated headers and knowledge bundles are wire-format contracts. Use exact byte/hash manifests:

```text
uv run python -m tests.support.regression.output_manifest create <output> --manifest <path>
uv run python -m tests.support.regression.output_manifest compare <expected> <actual>
```

Do not replace generated-header validation with normalized snapshots. A regression report records
source identity, producer/schema/configuration identity, cache state, sorted paths, byte counts,
and SHA-256 values. Preserve offsets, qualified names, inheritance, layouts, source locations,
DIE/CU provenance, and deterministic ordering.

## Property-based tests

Use Hypothesis for pure type-reference, declarator, array, qualifier, pointer, and parser
invariants. A property test supplements examples; it does not turn a unit test into an integration
test and does not replace a user-visible acceptance check. Keep failing examples reproducible and
bounded by the repository's normal test settings.

## Real assets and performance

Real PS4 checks require explicit local paths. They are never silently treated as a passing
replacement for required integration evidence.

```powershell
$env:DDON_REAL_PERFORMANCE = '1'
$env:DDON_REAL_ELF = 'D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf'
$env:DDON_REAL_DWARF_DUMP = "$env:DDON_REAL_ELF.llvmdwarfdump.zst"
$env:DDON_REAL_DWARF_INDEX = 'D:\ddon-dwarf-reconstructor\output\real-dump-index\DDOORBIS.elf.llvmdwarfdump.index.sqlite3'
$env:DDON_ORBIS_OBJDUMP = 'D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-objdump.exe'
uv run just test-performance
uv run just test-real-assets
```

Record cold/warm state, elapsed time, source identity, producer/configuration identity, and
manifest identity in the active Spec Kit feature. Preserve validated sidecars; do not routinely
delete them to make a benchmark pass.

## Nested specification project

The DWARF specification pipeline is a separate uv project with its own lockfile:

```text
uv run --directory tools/dwarf_spec_pipeline just test-unit
uv run --directory tools/dwarf_spec_pipeline just test-integration
uv run --directory tools/dwarf_spec_pipeline just test
uv run --directory tools/dwarf_spec_pipeline just test-official
uv run --directory tools/dwarf_spec_pipeline just check
```

The normal nested test excludes `official`/`real_artifact` checks. `test-official` is explicit
because it validates generated artifacts produced by the Docker/source-conversion workflow.

## Writing and reviewing tests

- Start from the behavior and choose the smallest layer that proves it.
- Add a deterministic integration or acceptance test when a change crosses a real boundary; do
  not rely only on mocks and coverage.
- Mark the scope and any purpose-specific qualifier in the test module or function.
- Keep unit tests fast and isolated; avoid broad real-DIE scans in the default loop.
- Mark performance tests as `performance` and `non_functional`, even when their current runtime is
  short.
- Use `pytest --markers` and `pytest --collect-only` to inspect the effective taxonomy.
- When a test is unavailable because an external prerequisite is absent, report it as unavailable
  evidence and keep the deterministic required tier green.

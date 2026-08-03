# Implementation Plan: Testing Pyramid and Validation Loop

## Baseline evidence

The root checkout currently collects 429 tests:

| Category observed | Count |
| --- | ---: |
| `unit` | 407 |
| `integration` | 2 |
| `performance` | 1 |
| `packaging` | 1 |
| No purpose/scope marker | 18 |

The declared markers are stricter than the actual taxonomy. `test_knowledge_exporter_integration.py`
contains deterministic output-boundary tests but is marked `unit`; quality and Sonar tests are
unmarked; and the normal `test`/coverage recipes rely on exclusions. The root CI invokes coverage
but has no separate required integration job. The nested specification project collects 15 tests
with `unit`/`integration` markers but has no purpose markers and its official-artifact assertion is
environment-gated.

## Design

### Marker model

Execution scopes are mutually exclusive:

- `unit`: isolated logic with mocked or in-memory boundaries.
- `integration`: multiple real project components with deterministic local fixtures.
- `acceptance`: user-visible CLI, installed distribution, or externally validated artifact flow.

Purpose markers are orthogonal:

- `functional`: behavior and output correctness.
- `regression`: a previously observed defect or stable output contract.
- `non_functional`: quality, performance, resource, maintainability, or operational behavior.

Qualifiers describe why selection may differ:

- `performance`, `slow`, `real_asset`, `packaging`, and `quality`.

The collection hook adds the ordinary `functional` purpose to tests with a valid `unit`,
`integration`, or `acceptance` scope only when a more specific purpose is not already declared;
quality/performance modules declare their non-functional purpose explicitly. It rejects missing or
ambiguous execution scopes and missing purposes. This keeps ordinary test files readable while
making omissions fail at collection time.

### Required command loop

- `test-unit`: fast unit scope only.
- `test-integration`: required deterministic integration only; real-asset integration is explicit.
- `test`: required correctness loop: all functional/regression unit and deterministic integration
  tests, excluding `performance`, `packaging`, and `real_asset` qualifiers.
- `test-without-integration`: explicit exceptional fast opt-out.
- `test-regression`: all regression contracts.
- `test-non-functional`: quality/non-functional tests other than performance where useful.
- `test-performance`: performance benchmarks, including explicit real-asset requirements.
- `package-smoke`: isolated distribution acceptance.
- `test-real-assets`: explicit local real-asset acceptance/performance selection.
- `coverage`/`coverage-ci`: the same required correctness selection as `test`.

The separate specification project gets `test-unit`, `test-integration`, `test`, and
`test-official` aliases while retaining its own lockfile and source-download boundary.

### Integration strategy

The knowledge exporter integration tests become required deterministic integration/regression
tests. They use a temporary ELF-shaped source, real source identity hashing, the exporter, actual
manifest/JSONL publication, and Orbis/DWARF evidence models. The real ELF generator tests remain
environmental acceptance tests with an explicit `real_asset` qualifier. This gives the default
loop a meaningful higher-level check without making proprietary files a prerequisite.

## Files to change

- Root configuration and runner: `pyproject.toml`, `justfile`, `tests/conftest.py`.
- Root test taxonomy: quality/tooling modules, exporter integration module, real-asset/performance
  module, packaging module, and taxonomy regression tests.
- Nested project configuration: `tools/dwarf_spec_pipeline/pyproject.toml`, its `justfile`,
  `tests/conftest.py`, and official-artifact test markers.
- User-facing docs: `README.md`, `tests/README.md`, `docs/reference/testing.md`,
  `docs/index.md`, the architecture explanations, and `tools/dwarf_spec_pipeline/README.md`.
- Durable instructions: `AGENTS.md`, `.github/copilot-instructions.md`,
  `.github/instructions/python.instructions.md`, and `CLAUDE.md`.
- Spec Kit and knowledge base: this feature directory and
  `docs/knowledge-base/testing/`.

## Validation tiers

1. Collection/taxonomy: `uv run pytest --collect-only`, marker audit, focused taxonomy tests.
2. Fast implementation: `uv run just test-unit`, `uv run just check`.
3. Required behavior: `uv run just test`, `uv run just coverage-ci`.
4. Explicit non-functional/distribution: `uv run just test-non-functional`, `uv run just
   test-performance` when paths are configured, `uv run just package-smoke`.
5. Handoff: `uv run just test`, `uv run just coverage-ci`, `uv run just audit`, nested `just
   check`/`just test`, and package checks when the distribution contract changes.

## Validation record

The completed implementation reports 433 root tests with 427 `unit`, 3 `integration`, and 3
`acceptance` scope markers; purpose and qualifier audits report zero unscoped or no-purpose items.
The required correctness selection passes 429 tests, the deterministic integration selection passes
2 tests, the opt-out selection passes 427 tests, and the non-functional selection passes 27 tests.
Coverage passes at 85.18% total line coverage with 74.7% branch coverage; the named high-risk
groups pass their configured thresholds. `check`, `audit`, package smoke, and the nested project's
normal test/check loops pass. Real-asset acceptance/performance and official-source checks remain
explicit and were not run without a selected external prerequisite.

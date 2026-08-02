# Feature Specification: Testing Pyramid and Validation Loop

**Feature branch:** `008-testing-pyramid-validation`
**Status:** Completed
**Owner:** DDON DWARF Reconstructor maintainers

## Problem

The repository has a large unit-test population but its test purpose and execution policy are
not consistently visible. The root configuration declares `unit`, `integration`, `performance`,
`slow`, and `packaging`, while 18 collected tests have no scope marker, the knowledge exporter
integration module is marked `unit`, and the normal recipes use exclusions rather than an explicit
required correctness tier. Real-asset tests can also skip when their input is unavailable, so
they cannot be the only evidence for the critical application workflow.

## Outcome

The repository shall have a documented and executable testing pyramid in which:

1. Every collected test has exactly one execution scope: `unit`, `integration`, or `acceptance`.
2. Every collected test has an explicit purpose, either `functional`, `regression`, or
   `non_functional`; `regression` may be combined with `functional`.
3. Performance, real-asset, packaging, quality-gate, and slow tests have dedicated qualifier
   markers and selection commands.
4. Required integration tests use deterministic local fixtures and run in the default correctness
   loop. Real proprietary assets remain explicit environmental acceptance tests.
5. An explicit fast opt-out can omit integration and acceptance scopes without changing the
   default loop.
6. The root and nested DWARF specification projects document compatible marker and command
   conventions, with their separate dependency and source boundaries preserved.
7. Documentation, Copilot/Codex/Python instructions, Spec Kit artifacts, and the testing
   knowledge base describe the same commands, marker policy, and evidence expectations.

## User stories and acceptance scenarios

### US1 - Understand test intent

As a maintainer, I can inspect a test's markers and understand whether it is unit, integration,
acceptance, functional, regression, or non-functional work.

**Acceptance scenarios:**

- `pytest --markers` lists every repository-owned marker with a useful description.
- Collection fails with a clear error if a test has no valid execution scope or no purpose marker.
- Collection succeeds with `--strict-markers` and the taxonomy audit reports zero unclassified
  tests.

### US2 - Exercise required functional behavior

As a maintainer, the default correctness recipe exercises unit tests and deterministic integration
tests, including the application export path, without requiring a proprietary ELF.

**Acceptance scenarios:**

- `uv run just test` runs unit and required integration/acceptance tests and excludes only
  explicitly non-required categories such as performance, packaging, and unavailable real assets.
- The required exporter integration tests write and verify a manifest and JSONL evidence bundle in
  a temporary directory.
- `uv run just test-without-integration` provides an explicit fast opt-out and is documented as
  an exceptional iteration shortcut rather than the default quality gate.

### US3 - Keep non-functional work visible

As a maintainer, I can run performance, packaging, quality, and real-asset checks intentionally
and distinguish their evidence from functional correctness.

**Acceptance scenarios:**

- The real `rLayout` budget is marked `performance`, `non_functional`, `integration`, `slow`, and
  `real_asset`, and its command documents the required environment.
- The package installation smoke test is marked `acceptance`, `functional`, and `packaging` and
  remains separate because it creates an isolated uv tool environment.
- Quality and tooling checks are marked `unit` plus `non_functional` and/or `quality`.

### US4 - Reproduce the loop across clients and projects

As a Codex, Copilot, or Python-tooling user, I can follow one authoritative loop and know which
instructions and artifacts to update when a test contract changes.

**Acceptance scenarios:**

- `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/python.instructions.md`,
  `CLAUDE.md`, README/testing documentation, and the active Spec Kit feature agree on the loop.
- The nested `tools/dwarf_spec_pipeline` project retains its dependency boundary and documents
  the same scope/purpose vocabulary where it applies.
- The knowledge-base note records the baseline gap, the new policy, and the validation evidence.

## Non-goals

- Making the proprietary PS4 ELF or 30+ GB compressed DWARF dump a CI dependency.
- Treating coverage percentage as a substitute for functional, regression, integration, or
  non-functional evidence.
- Replacing exact generated-header manifest comparisons with snapshots.
- Introducing a second test runner or a general-purpose testing plugin.

## Constraints

- Preserve immutable source and cache policy; no real inputs, generated headers, logs, or runtime
  caches may be committed.
- Keep deterministic ordering, source offsets, qualified names, layout facts, and provenance
  unchanged.
- Use `uv run` and the canonical `just` recipes for Python tooling.
- Keep test taxonomy enforcement on the pytest configuration boundary, not in production domain
  code.

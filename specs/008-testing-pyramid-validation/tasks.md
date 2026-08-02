# Tasks: Testing Pyramid and Validation Loop

## Baseline and policy

- [x] T001 Inventory root and nested pytest markers, collection counts, `justfile` recipes, CI,
  instruction surfaces, and documentation claims. Validation: collection-only and read-only
  repository inspection.
- [x] T002 Record the 429-test root baseline and 15-test nested baseline in `plan.md`.
- [x] T003 Add the scope/purpose/qualifier contract and collection-time taxonomy enforcement in
  `tests/conftest.py`; add focused tests in `tests/quality/test_test_taxonomy.py`. Validation tier:
  collection/taxonomy.

## Root test loop

- [x] T004 Add explicit markers to all currently unclassified root test modules, including quality,
  Sonar, parser, and output-manifest tests. Validation tier: collection/taxonomy.
- [x] T005 Reclassify exporter output tests as deterministic integration/regression tests and keep
  real ELF generator tests explicitly `real_asset` acceptance tests. Validation tier: required
  behavior plus real-asset selection.
- [x] T006 Add or strengthen a required integration assertion for manifest/JSONL output and source
  identity publication using only temporary deterministic fixtures. Validation tier: required
  behavior.
- [x] T007 Register all markers and update root recipes so integration is included by default,
  while `test-without-integration` is an explicit opt-out. Validation tier: collection and
  required behavior.
- [x] T008 Align coverage and CI selection with the required correctness loop and add a visible
  integration stage or equivalent report. Validation tier: required behavior/CI configuration.

## Nested specification project

- [x] T009 Add purpose markers and compatible command aliases to the nested project; classify the
  official artifact assertion as an explicit official/real-artifact acceptance check. Validation
  tier: nested unit/integration collection and test.

## Documentation and durable guidance

- [x] T010 Rewrite `docs/TESTING.md` and `tests/README.md` around the executable taxonomy and
  command matrix; correct stale counts and opt-in language.
- [x] T011 Update README, architecture, docs index, and nested README links and claims.
- [x] T012 Update `AGENTS.md`, Copilot, Python, and Claude instructions so the same test loop and
  evidence rules are applied by every client.
- [x] T013 Add the testing-pyramid knowledge-base note with source links, baseline findings,
  decisions, and validation evidence.
- [x] T014 Update this feature's plan/spec/tasks/checklist status after implementation and record
  deferred real-asset/official-source prerequisites explicitly.

## Handoff validation

- [x] T015 Run `uv run just test-unit` and `uv run just check` after each refactoring slice.
- [x] T016 Run `uv run just test`, `uv run just coverage-ci`, and `uv run just audit`.
- [x] T017 Run root package checks and nested pipeline checks where applicable; run real-asset and
  official-source checks only with explicit local paths/flags and record skipped prerequisites.

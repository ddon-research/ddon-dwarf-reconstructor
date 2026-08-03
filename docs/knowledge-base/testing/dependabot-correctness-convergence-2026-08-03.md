# Dependabot correctness convergence (2026-08-03)

## Scope

This note records the evidence-led goal run for the seven open Dependabot pull requests in
`ddon-research/ddon-dwarf-reconstructor`. The objective was to validate the proposed dependency
and GitHub Action updates, reproduce the shared correctness failure, and repair the product
contract without weakening source-bound cache reuse.

## Confirmed remote evidence

`gh auth status`, `gh pr list`, `gh pr diff`, `gh pr checks`, and `gh run view --log-failed` were
run against the repository. PRs 1 through 7 are open Dependabot updates:

| PRs | Proposed change | Non-correctness checks | Correctness check |
| --- | --- | --- | --- |
| #1 | publish-unit-test-result-action SHA | pass | fail |
| #2 | codecov/codecov-action SHA | pass | fail |
| #3 | actions/checkout SHA | pass | fail |
| #4 | actions/setup-python SHA | pass | fail |
| #5 | nested pytest-cov upper bound | pass | fail |
| #6 | astral-sh/setup-uv SHA | pass | fail |
| #7 | nested pytest upper bound | pass | fail |

The seven required-test jobs all fail at the same regression:
`tests/infrastructure/test_artifacts.py::test_catalog_reuses_identity_after_source_relocation`.
PR #7 is the referenced run: [job 91567057120](https://github.com/ddon-research/ddon-dwarf-reconstructor/actions/runs/30774416064/job/91567057120).
The failure is `AssertionError: relocation rehashed the complete source`; the log also contains a
secondary 403 from the test-result publisher when it tries to create a check run. That publisher
permission failure is not the correctness root cause.

## Root cause

The catalog lookup key previously included `st_ctime_ns`. Linux changes ctime when a file is
renamed, while content, size, mtime, device, and inode remain stable. The Windows development
host therefore passed the relocation test while the Ubuntu CI runner rehashed the moved source.

## Refactor contract

The shared source-identity policy now:

- uses size, mtime, device, and inode for the relocation-stable metadata key;
- retains ctime and recorded paths to reject same-path mutation;
- accepts ctime-only drift only when the recorded path disappeared and the new path has the same stable object metadata;
- returns the recorded identity metadata after relocation so downstream fingerprints and caches stay warm;
- keeps `verify=True` as the explicit complete-source SHA-256 boundary; and
- keeps malformed catalogs, atomic writes, and lock recovery on the existing failure paths.

A new regression synthesizes ctime-only drift at an existing path and asserts that it still
rehashes. The relocation test remains a full source-hash spy and asserts that no second hash is
performed.

## Validation record

Focused local evidence after the refactor:

- `uv run pytest tests/infrastructure/test_artifacts.py -m unit -q`: 12 passed.
- Source-bound lazy-index and cache tests: 27 passed.
- `uv run pyrefly check --min-severity warn`: passed with zero diagnostics.
- `uv run just check`: passed; Ruff, formatting, Pyrefly, deptry, structure, and architecture
  checks are green.
- `uv run just test-unit`: 445 passed, 6 deselected.
- `uv run just test`: 447 passed, 4 deselected.
- `uv run just coverage-ci`: 447 passed, 4 deselected; 84.87% total coverage, with parsing,
  generation, orchestration, and artifact groups above their line and branch thresholds.
- `uv run just audit`: zero Prospector diagnostics.
- `uv run --directory tools/dwarf_spec_pipeline just test`: 17 passed, 1 deselected.
- `uv run --directory tools/dwarf_spec_pipeline just test-official`: 1 skipped, 17 deselected
  because the official external prerequisite is not present.
- `uv run --directory tools/dwarf_spec_pipeline just check`: passed; Ruff, formatting, Pyrefly,
  and deptry are green.

Post-fix remote convergence completed. PRs #1-6, #8, and #9 merged after green correctness,
quality, and nested-pipeline checks; the conflicted Dependabot PR #7 was closed as superseded by
the conflict-free replacement #8. The final `main` commit `6d78943` passed the Required
Correctness Tests and Coverage, Code Quality, Dependency Graph, and DWARF Specification Pipeline
workflows. PR #9 synchronized `tools/dwarf_spec_pipeline/uv.lock` with the merged pytest and
pytest-cov bounds. T025 is complete. Real PS4, compiler, and proprietary tool evidence remain
explicit environment-gated checks.

# CI and GitHub Actions hardening (2026-08-03)

## Scope

This note records the evidence-led CI audit for `ddon-research/ddon-dwarf-reconstructor`. The
objective was to align hosted validation with the local uv/just contract, refresh action references,
add low-effort public-repository security integrations, and improve the durable Copilot/Codex/Claude
instructions without making proprietary assets or paid GitHub features part of correctness.

## Confirmed remote evidence

Read-only `gh` inspection confirmed:

- The repository is public and `main` is the default branch.
- Code Quality, Required Correctness Tests and Coverage, and DWARF Specification Pipeline are
  checked-in workflows. GitHub also runs managed Dependabot Updates and Dependency Graph workflows.
- `main` has no branch-protection rules or required status checks.
- CodeQL has no prior analysis. Secret scanning and Dependabot security updates are disabled in
  `security_and_analysis`.
- The only current Dependabot alert is a fixed medium-severity `pytest` alert in
  `tools/dwarf_spec_pipeline/uv.lock`.
- Current release mappings used by the change are:

| Action | Version | Commit |
| --- | --- | --- |
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-python` | v7.0.0 | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| `astral-sh/setup-uv` | v9.0.0 | `c771a70e6277c0a99b617c7a806ffedaca235ff9` |
| `codecov/codecov-action` | v7.0.0 | `fb8b3582c8e4def4969c97caa2f19720cb33a72f` |
| `actions/upload-artifact` | v7.0.1 | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `EnricoMi/publish-unit-test-result-action` | v2.24.0 | `d0a4676d0e0b938bc201470d88276b7c74c712b3` |
| `actions/dependency-review-action` | v5.0.0 | `a1d282b36b6f3519aa1f3fc636f609c47dddb294` |
| `github/codeql-action` | v4.37.5 | `d1ba80a13dd99fba24a470575428917156a28b43` |

## Implemented changes

- Centralized Python/uv setup, frozen installation, and lockfile-keyed caching in a local composite
  action.
- Added `actionlint -color` to the root `just check` gate. The hosted quality job downloads the
  fixed v1.7.12 Linux release and verifies SHA-256 before invoking the same recipe.
- Made Prospector a blocking Code Quality step.
- Added timeouts, manual dispatch, concurrency cancellation, shallow credential-free checkout,
  bounded artifact retention, and full-SHA action pins.
- Added Dependency Review for pull requests and CodeQL scans for Python plus GitHub Actions.
- Restricted test-result publishing to same-repository events with `checks: write` and
  `comment_mode: off`; fork PRs still receive artifacts.
- Grouped minor/patch GitHub Action Dependabot updates.

## Validation evidence and remaining boundary

The final checkout validation passed on this Windows host:

- `actionlint` 1.7.12 passed for the checked-in workflow files, including the local composite
  action references used by those workflows.
- All external action release tags matched their pinned full commit SHAs; no mutable references
  were found.
- Root `test-unit` passed 445 tests; `check` passed all quality checks; `test` and `coverage-ci`
  passed 447 tests with 4 explicit exclusions and 84.87% total coverage; `audit` passed with zero
  Prospector messages.
- Nested `just test` passed 17 tests with one explicit deselection, nested `just check` passed, and
  `just test-official` recorded one skip for unavailable official artifacts.

GitHub-hosted execution of the new workflows remains post-publication remote evidence. The
read-only baseline captured before this checkout change is still the source for the settings
boundary below.

Settings follow-up remains explicit: enable public secret scanning and Dependabot security updates,
then require the correctness, quality, nested-pipeline, Dependency Review, and CodeQL checks in
branch protection. Those changes require remote administrator action and were intentionally not
performed from the checkout.

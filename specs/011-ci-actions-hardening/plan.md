# Implementation Plan: CI and GitHub Actions Hardening

## Baseline evidence

Read-only local and GitHub evidence on 2026-08-03 established:

- Root `uv run just test-unit`, `uv run just check`, `uv run just audit`, and nested
  `uv run --directory tools/dwarf_spec_pipeline just check` passed.
- The root repository is public. The dependency graph and Dependabot version-update workflows are
  active; the only current Dependabot alert is fixed.
- `main` has no branch-protection rules. CodeQL has no prior analysis, and live secret scanning
  plus Dependabot security updates are disabled.
- `setup-uv` was pinned to v6 while v9.0.0 is current; `upload-artifact` was pinned to v4
  while v7.0.1 is current. Checkout v7.0.1, setup-python v7.0.0, Codecov v7.0.0, and
  publish-unit-test-result-action v2.24.0 match current release refs.
- The test-result publisher previously had a secondary 403 because its check permission was not
  granted. The correctness command itself remained the authoritative pass/fail signal.

## Design

- Add `.github/actions/setup-python-uv/action.yml` for Python 3.14.6, setup-uv v9, lockfile-keyed
  caching, and frozen installation.
- Update the three existing workflows with manual dispatch, concurrency cancellation, timeouts,
  shallow credential-free checkout, and the composite setup action.
- Make Prospector blocking and grant only the test job's `checks: write` permission. Skip the
  publisher on fork pull requests while retaining artifacts.
- Add public-repository Dependency Review and CodeQL Advanced workflows. CodeQL analyzes `python`
  and `actions` with the current v4.37.5 action SHA.
- Add an `actionlint` recipe to the root `just` contract and include it in `just check`; the hosted
  quality job downloads actionlint v1.7.12 for the fixed Linux runner and verifies its SHA-256
  before invoking that recipe.
- Group minor/patch GitHub Action Dependabot updates while keeping major updates visible.
- Add a CI documentation page, workflow-specific Copilot instructions, a CI goal template, and
  synchronized durable/spec/knowledge-base guidance.

## Files

- Workflow/action configuration: `.github/actions/setup-python-uv/action.yml`,
  `.github/workflows/*.yml`, `.github/dependabot.yml`.
- Durable guidance: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`,
  `.github/instructions/github-actions.instructions.md`.
- User docs: `README.md`, `docs/CI.md`, `docs/README.md`, `docs/TESTING.md`,
  `docs/ARCHITECTURE.md`, `docs/GOAL_WORKFLOW.md`.
- Evidence: `docs/knowledge-base/testing/ci-actions-hardening-2026-08-03.md` and this feature.

## Validation tiers

1. Configuration: inspect all `uses:` refs, verify release-to-SHA mappings, inspect Dependabot
   schema, and run workflow syntax validation with `actionlint` when available.
2. Fast root: `uv run just test-unit` and `uv run just check`.
3. Required root: `uv run just test`, `uv run just coverage-ci`, and `uv run just audit`.
4. Nested: `uv run --directory tools/dwarf_spec_pipeline just test` and `just check`.
5. Remote: inspect workflow registration, action runs, security settings, and branch protection
   read-only; do not claim remote Settings changes without an explicit administrator action.

## Final validation evidence

- `actionlint` 1.7.12 passed for all checked-in workflow files, including the local composite
  action references used by those workflows.
- Release-tag-to-SHA verification passed for every external action reference; no mutable refs were
  found.
- Root `uv run just test-unit` passed 445 tests; `uv run just check` passed all lint, typing,
  dependency, structure, and architecture checks.
- Root `uv run just test` and `uv run just coverage-ci` passed 447 tests with 4 explicit
  exclusions; total coverage was 84.87% and the named coverage groups passed.
- Root `uv run just audit` passed with zero Prospector messages.
- Root `uv run just package-smoke` passed; the `just check` output included the actionlint recipe.
- Nested `uv run --directory tools/dwarf_spec_pipeline just test` passed 17 tests with one
  explicit deselection; `just test-official` skipped its unavailable official-artifact test;
  nested `just check` passed.
- New hosted workflow runs and administrator-owned Settings changes remain post-publication
  evidence. The live branch-protection, secret-scanning, Dependabot-security-update, and CodeQL
  baseline was recorded before the checkout change and is not claimed as changed here.

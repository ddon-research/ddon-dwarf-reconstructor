# Tasks: CI and GitHub Actions Hardening

## Evidence and design

- [x] T001 Capture worktree, local gate, remote workflow, action-release, Dependabot, security-setting,
  and branch-protection evidence before editing.
- [x] T002 Compare the local `just` contract with each hosted workflow and record mismatches.
- [x] T003 Read current Codex goal, GitHub Actions, GitHub security, and awesome-copilot guidance.

## Workflow refactor

- [x] T004 Add the shared Python/uv composite action with lockfile-keyed caching and frozen sync.
- [x] T005 Update existing workflows with current SHAs, checkout hardening, timeouts, dispatch,
  concurrency, and local parity.
- [x] T006 Make Prospector blocking and repair same-repository test-result check permissions while
  keeping fork PRs artifact-only.
- [x] T007 Add Dependency Review and CodeQL workflows using public-repository features.
- [x] T008 Group minor/patch GitHub Action Dependabot updates and preserve major-update visibility.

## Instructions and evidence

- [x] T009 Add workflow-specific Copilot instructions derived from the reviewed GitHub guidance.
- [x] T010 Update AGENTS, Copilot, Claude, README, architecture, testing, and goal workflow docs.
- [x] T011 Record free-plan assumptions and live remote-setting gaps in the CI documentation.
- [x] T012 Add this Spec Kit feature and testing knowledge-base record.

## Validation and convergence

- [x] T013 Validate workflow syntax and action references after the final diff.
- [x] T014 Run root `test-unit`, `check`, `test`, `coverage-ci`, and `audit`.
- [x] T015 Run nested `test` and `check`, inspect the final diff, and record any blocked external
  settings or real-asset evidence.
- [x] T016 Mark this feature complete only after the named evidence surface passes.

## Actionlint integration follow-up

- [x] T017 Add the local `actionlint` recipe and include it in the root `just check` gate.
- [x] T018 Install and checksum-verify actionlint v1.7.12 in the hosted Code Quality adapter.
- [x] T019 Update the CI/instruction/spec evidence and rerun the workflow plus local validation
  loop.

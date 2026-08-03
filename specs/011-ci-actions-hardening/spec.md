# Feature Specification: CI and GitHub Actions Hardening

**Feature branch:** `011-ci-actions-hardening`
**Status:** Complete
**Owner:** DDON DWARF Reconstructor maintainers

## Problem

The repository's local validation contract is stronger than its hosted CI adapter. The quality
workflow softened Prospector failures, Python/uv setup was duplicated across workflows, two action
pins were stale, the test-result publisher lacked the check permission it needs, and the repository
had no checked-in Dependency Review or CodeQL workflow. Live GitHub settings also need to be
distinguished from checkout-owned configuration so free-plan assumptions remain explicit.

## Outcome

The repository shall have a reproducible, security-conscious CI adapter in which:

1. Root Code Quality runs `just check`, package smoke, and blocking `just audit`.
2. Required Correctness Tests and Coverage runs taxonomy collection and the default coverage
   selection, including deterministic integration tests, without proprietary assets.
3. The nested DWARF specification workflow uses its independent uv project and lockfile.
4. Python/uv setup, caching, action pins, timeouts, checkout credentials, and concurrency policy
   have one checked-in implementation where practical.
5. Every hosted action is pinned to a verified full commit SHA with a readable release comment.
6. Local and hosted workflow syntax validation uses actionlint v1.7.12; hosted CI verifies the
   pinned release artifact before invoking the canonical check recipe.
7. Dependency Review and CodeQL for Python and GitHub Actions are available through public-repository
   GitHub features without introducing paid-plan, cloud-secret, or proprietary-runner dependencies.
8. AGENTS, Copilot, Claude, README, architecture/testing docs, Spec Kit, and the testing knowledge
  base describe the same local/remote evidence contract.
9. Remote branch protection, secret scanning, and Dependabot security-update settings are reported
   as explicit administrator follow-ups rather than being implied by a local file edit.

## Acceptance scenarios

- A workflow change can run the same root or nested `uv run just` recipe locally and in CI.
- A stale action is updated only after its release tag and commit SHA are checked through GitHub.
- A failing Prospector command fails the Code Quality job.
- A fork pull request can still produce test and coverage artifacts without receiving a privileged
  write token for the test-result check.
- A pull request receives a dependency-review job, and CodeQL analyzes Python and workflow files on
  pushes, pull requests, and the weekly schedule.
- `gh api repos/ddon-research/ddon-dwarf-reconstructor --jq '.security_and_analysis'` and branch
  protection inspection are recorded separately from the checked-in workflow diff.
- The complete local root and nested validation loop remains green.

## Non-goals

- Enabling or changing GitHub repository Settings, branch protection, secrets, billing, or plan
  entitlements from the checkout.
- Making the PS4 ELF, compressed DWARF dump, Sony SDK, compiler, Orbis tools, or performance
  benchmark hosted CI prerequisites.
- Making Codecov or a third-party reporter the source of correctness truth.
- Replacing the canonical `just` automation source with ad-hoc shell wrappers.

## Constraints

- Preserve deterministic integration selection, source identity, cache provenance, output bytes, and
  explicit real-asset/performance evidence.
- Keep root and `tools/dwarf_spec_pipeline` as independent uv projects.
- Use least-privilege GitHub tokens and immutable action references.
- Do not commit generated caches, artifacts, credentials, or external binaries.
- Keep documentation and instructions CommonMark-compatible and synchronized.

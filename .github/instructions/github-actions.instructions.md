---
description: 'Secure, reproducible GitHub Actions guidance for the DDON DWARF reconstructor'
applyTo: '.github/workflows/**/*.yml,.github/workflows/**/*.yaml,.github/actions/**/*'
---

# GitHub Actions instructions

These rules supplement `AGENTS.md` and keep hosted automation aligned with the local `uv` and
`just` contracts. Read [docs/CI.md](../../docs/CI.md) before changing a workflow, composite
action, or Dependabot configuration.

## Workflow design

- Give every workflow and step a descriptive name. Use `push` and `pull_request` for the `main`
  branch, `workflow_dispatch` for safe manual reruns, and a narrow weekly `schedule` only for
  security scans.
- Add workflow-level concurrency with a branch/PR-specific group and
  `cancel-in-progress: true` for CI and analysis runs. Add a realistic `timeout-minutes` to every
  hosted job.
- Keep workflows thin. Checkout first with `fetch-depth: 1` and `persist-credentials: false`,
  then use `./.github/actions/setup-python-uv` for Python 3.14.6, uv caching, and
  `uv sync --python 3.14.6 --frozen`. The nested `tools/dwarf_spec_pipeline` project must pass
  its own working directory and lockfile boundary.
- Call the canonical recipes instead of reproducing their commands: `just check` (including
  `actionlint`), `just audit`, `just coverage-ci`, and the nested project's `just ci`. Do not make
  real PS4 assets, expanded dumps, compilers, Sony SDKs, proprietary tools, or performance budgets
  hosted CI prerequisites.

## Supply-chain and token security

- Pin every external `uses:` reference, including GitHub-owned and third-party action dependencies,
  to a full 40-character commit SHA with a human-readable release comment. Local composite action paths
  are repository source and must be reviewed with the workflow diff. Use Dependabot for discovery,
  verify the tag-to-SHA mapping with `gh`, and never use `@main`, `@latest`, or a mutable
  major tag.
- Set `permissions: contents: read` by default. Grant a job only the write permission it proves it
  needs: CodeQL gets `security-events: write`, and the same-repository test-result publisher gets
  `checks: write`. Do not add broad `contents: write`, `pull-requests: write`, or `id-token: write`
  without an explicit deployment/use case.
- Do not use `pull_request_target` together with checkout or execution of contributor-controlled
  code. Fork pull requests must remain useful with read-only tokens and artifacts, without secrets.
- Never print secrets, full binary contents, generated headers, credentials, or unbounded command
  output. Prefer GitHub Secrets and short-lived OIDC credentials for any future cloud integration.

## Free public-repository integrations

- Dependency Review is a pull-request gate for newly introduced vulnerable dependencies.
- CodeQL scans Python and GitHub Actions workflow code on pushes, pull requests, and a weekly
  schedule. Keep its `security-events: write` permission and action SHA explicit.
- Dependabot monitors both root and nested uv projects plus GitHub Actions. Group only minor/patch
  action updates; keep major updates individually visible.
- Treat the dependency graph, secret scanning, branch protection, and Dependabot security updates
  as GitHub Settings state. Record their live status with `gh api`; do not claim a checkout edit
  enabled a remote feature. This repository is public, so use public-repository availability and
  do not introduce paid GitHub Code Security, private-repository-only features, or commercial
  scanners into the correctness contract.
- GitHub artifacts are the durable test-report handoff. Keep retention bounded. Codecov is
  advisory and must not replace `coverage-ci`.

## Review and validation loop

Before editing CI or Dependabot files, capture:

```text
gh auth status
gh pr list --repo ddon-research/ddon-dwarf-reconstructor --state open
gh pr diff <pr-number> --repo ddon-research/ddon-dwarf-reconstructor
gh pr checks <pr-number> --repo ddon-research/ddon-dwarf-reconstructor
gh run view <run-id> --repo ddon-research/ddon-dwarf-reconstructor --log-failed
```

After each cohesive slice, run `uv run just actionlint` (or `uv run just check`, which includes it),
then run the focused local command, `uv run just test-unit`, `uv run just check`, and `uv run just
test`. Before handoff also run `uv run just coverage-ci`, `uv run just audit`, and the applicable
nested project checks. Separate confirmed, blocked, and deferred remote-setting evidence.

## Documentation changes

When CI behavior changes, update `docs/CI.md`, `docs/TESTING.md`, `docs/ARCHITECTURE.md`, the active
Spec Kit feature, the testing knowledge base, and the Copilot/Claude adapters as applicable. Use
CommonMark-compatible headings, blank lines around lists and code blocks, fenced blocks with a
language where syntax is shown, valid descriptive links, and tables for repeated mappings.

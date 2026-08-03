# CI and GitHub Actions

This repository keeps GitHub Actions as a thin remote adapter over the same locked `uv` and
`just` commands used locally. The workflows must prove deterministic correctness and tooling
quality; real PS4 assets, compiler installations, proprietary SDKs, and performance budgets stay
explicit local evidence.

## Workflow contract

| Workflow | Trigger | Required evidence |
| --- | --- | --- |
| Code Quality | Push, pull request, manual | `uv run just check` (including actionlint), `package-smoke`, and blocking `uv run just audit` |
| Required Correctness Tests and Coverage | Push, pull request, manual | Taxonomy collection, required deterministic integration collection, `uv run just coverage-ci`, coverage report, JUnit and coverage artifacts |
| DWARF Specification Pipeline | Push, pull request, manual | Nested `uv run just ci` and Docker Compose configuration validation |
| Dependency Review | Pull request, manual | GitHub dependency review for introduced vulnerable dependencies |
| CodeQL Advanced | Push, pull request, weekly schedule, manual | CodeQL analysis for Python and GitHub Actions workflows |

The checked-in composite action at
`.github/actions/setup-python-uv/action.yml` centralizes the Python 3.14.6, uv, cache, and frozen
dependency setup. The nested specification project passes its own directory so its independent
lockfile and environment remain separate.

The default correctness selection is unchanged:

```text
-m "not performance and not packaging and not real_asset"
```

That selection includes deterministic integration tests. `real_asset`, `performance`, `packaging`,
official-source, Docker conversion, MSVC, and proprietary-tool checks are not silently substituted
by a green hosted runner.

## Local parity loop

Use the same commands before opening a pull request:

```text
uv run just test-unit
uv run just check
uv run just test
uv run just coverage-ci
uv run just audit
uv run --directory tools/dwarf_spec_pipeline just test
uv run --directory tools/dwarf_spec_pipeline just check
```

`uv run just check` includes `actionlint -color`, which scans the repository's workflow files. On
Windows, install actionlint v1.7.12 with `winget install --id rhysd.actionlint --exact --version
1.7.12` and start a new terminal so the WinGet Links directory is visible on `PATH`; on other
systems use the package manager or release binary from
the [actionlint installation guidance](https://github.com/rhysd/actionlint/blob/v1.7.12/docs/install.md).

The hosted workflows use shallow, credential-free checkouts, the built-in uv cache keyed by
`uv.lock`, explicit timeouts, manual dispatch, and concurrency cancellation for superseded runs.
The quality job downloads the pinned actionlint v1.7.12 Linux binary, verifies its release
SHA-256, adds it to `PATH`, and then invokes the same `just check` recipe used locally.
The test-results check is published only when the token can write checks for the same repository;
fork pull requests still retain the JUnit and coverage artifacts without receiving a privileged
token. Codecov remains advisory (`fail_ci_if_error: false`); the repository's own coverage command
is the correctness gate.

## Security and free-plan boundary

All external actions are pinned to full commit SHAs with a version comment. Dependabot monitors the
actions and both uv projects; minor and patch GitHub Action updates are grouped to keep review effort
bounded, while major updates remain visible. Workflow defaults are read-only, and write access is
limited to CodeQL's `security-events` upload and the test-results check publisher.

The repository is public. GitHub documents CodeQL code scanning, secret scanning, the dependency
graph, and dependency review as available to public repositories; the new workflows use those
public-repository features without adding private-repository-only or paid Code Security features.
CodeQL still consumes hosted Actions runtime, so the weekly schedule is deliberately the only
periodic scan. No release attestation, deployment environment, cloud credential, OIDC provider,
paid third-party scanner, or proprietary runner is required by this CI contract.

The following live repository settings were read on 2026-08-03 and were not changed by a checkout
edit:

- `main` has no branch-protection rules or required status checks.
- CodeQL default setup has not produced an analysis yet; the checked-in workflow is the source of
  truth for the new scan.
- Secret scanning and Dependabot security updates are disabled in the repository settings even
  though the repository is public.
- The dependency graph and Dependabot version-update workflows are active, and the only current
  Dependabot alert is fixed.

An administrator should enable the free public-repository secret scanning and Dependabot security
updates settings, then require the correctness, quality, nested-pipeline, dependency-review, and
CodeQL checks in branch protection. Those are GitHub Settings changes, not mutations performed by
this code change.

## Workflow change review

For a workflow or Dependabot change, capture remote evidence before editing:

```text
gh auth status
gh pr list --repo ddon-research/ddon-dwarf-reconstructor --state open
gh pr checks <pr-number> --repo ddon-research/ddon-dwarf-reconstructor
gh run view <run-id> --repo ddon-research/ddon-dwarf-reconstructor --log-failed
gh api repos/ddon-research/ddon-dwarf-reconstructor --jq '.security_and_analysis'
```

Validate the YAML/workflow semantics with `uv run just actionlint`, then run the local parity loop.
Do not use `pull_request_target` to execute checkout code from an untrusted
pull request, do not log secrets, and do not replace full-SHA pins with mutable tags.

## References

- [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [Building and testing Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [GitHub supply-chain security](https://docs.github.com/en/code-security/concepts/supply-chain-security/supply-chain-security)
- [Code scanning and CodeQL](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-code-scanning)
- [Secret scanning](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning)
- [Dependency graph](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-graph)
- [Dependabot configuration](https://docs.github.com/en/code-security/concepts/supply-chain-security/about-the-dependabot-yml-file)
- [GitHub Actions workflow concepts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows)
- [actionlint usage](https://github.com/rhysd/actionlint/blob/v1.7.12/docs/usage.md)
- [actionlint configuration](https://github.com/rhysd/actionlint/blob/v1.7.12/docs/config.md)
- [actionlint installation](https://github.com/rhysd/actionlint/blob/v1.7.12/docs/install.md)
- [GitHub Actions CI/CD best practices](https://github.com/github/awesome-copilot/blob/main/instructions/github-actions-ci-cd-best-practices.instructions.md)
- [GitHub Actions expert agent](https://github.com/github/awesome-copilot/blob/main/agents/github-actions-expert.agent.md)
- [awesome-copilot instruction authoring](https://github.com/github/awesome-copilot/blob/main/instructions/instructions.instructions.md)
- [awesome-copilot Markdown instructions](https://github.com/github/awesome-copilot/blob/main/instructions/markdown.instructions.md)
- [awesome-copilot Markdown content guidance](https://github.com/github/awesome-copilot/blob/main/instructions/markdown-content-creation.instructions.md)

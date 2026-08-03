# Goal-oriented DWARF research workflow

This repository uses Codex goals for long-running investigations whose finish line is clear but
whose implementation path may change as evidence arrives. A goal is scoped to the current Codex
thread; it does not replace `AGENTS.md`, the active Spec Kit feature, or durable project policy.

The official Codex guidance is [Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex).
The useful project shape is:

```text
/goal Bring the DDON DWARF parser to an evidence-backed DWARF2-4 correctness baseline,
verified by all-CU ELF and LLVM-dump producer evidence, semantic-specification checks,
focused regressions, and the required validation gates, while preserving deterministic
provenance, offsets, cache identity, output bytes, and bounded memory. Use only the
checkout, explicit local assets, generated specification artifacts, and documented tool
surfaces. Between iterations, inspect evidence, make one cohesive refactoring slice, and
run the smallest relevant tests plus `uv run just check`. If blocked, report the exact
missing prerequisite and the action that would unlock it.
```

## Iteration stages

Before changing code for a CI or Dependabot problem, capture the remote evidence surface:

```text
gh auth status
gh pr list --repo ddon-research/ddon-dwarf-reconstructor --state open
gh pr diff <pr-number> --repo ddon-research/ddon-dwarf-reconstructor
gh pr checks <pr-number> --repo ddon-research/ddon-dwarf-reconstructor
gh run view <run-id> --repo ddon-research/ddon-dwarf-reconstructor --log-failed
```

A passing action-update, dependency-update, lint, or nested-tool check validates only that
proposal's surface. The goal remains active until the required correctness job is reproduced and
the local and remote evidence agree.

A suitable maintenance goal for this loop is:

```text
/goal Resolve all open Dependabot correctness failures, verified by gh pr checks, focused
reproduction, uv run just test-unit, uv run just check, uv run just test, coverage-ci, and audit,
while preserving deterministic source identity, cache reuse, provenance, and output bytes. Use
the checkout, explicit local assets, and gh evidence. Between iterations record the observed
failure, the smallest safe change, and the next validation. If a remote permission, asset, or
tooling prerequisite blocks progress, report it with the exact unlock action.
```

For a repository-wide CI/Actions audit, make the completion contract explicit before starting:

```text
/goal Bring ddon-dwarf-reconstructor CI into parity with the local uv/just validation contract,
verified by the checked-in workflow files, current action release SHAs, GitHub workflow runs,
`uv run just test-unit`, `uv run just check`, `uv run just test`, `uv run just coverage-ci`,
`uv run just audit`, and the nested project's checks, while preserving deterministic integration
coverage, explicit real-asset boundaries, least-privilege tokens, and free public-repository
features. Use only this checkout, read-only gh evidence, official GitHub/OpenAI documentation,
and the named awesome-copilot guidance. Between iterations, record the observed CI/local mismatch,
make one cohesive workflow or instruction slice, and run the smallest relevant validation before
the full loop. If a GitHub Settings change requires remote administrative authorization, record it
as a bounded follow-up with the exact setting and unlock action; do not treat it as silently done.
```

This template names the outcome, verification surface, constraints, boundaries, iteration policy,
and blocked condition. It also keeps remote settings changes separate from checkout edits, which
makes a final handoff auditable.

1. Establish the evidence surface: inspect the worktree, identify immutable inputs, and run
   `artifacts inspect-elf` and `artifacts inspect-dwarf-dump` when explicit local paths are present.
2. Inventory external binary tools and their local `--version`/`--help` output. Select only
   named bounded profiles, with Orbis tools as PS4 ABI authority and generic tools recorded as
   additive cross-checks. Publish source-bound manifests before attaching evidence to a graph.
3. Build or validate the specification index with
   `uv run --project tools/dwarf_spec_pipeline dwarf-spec-pipeline audit --output-dir
   docs/knowledge-base/dwarf-specification/generated --source-root src`.
4. Convert each suspected relationship into a focused test or a documented, intentionally deferred
   contract. Preserve producer facts; derived checks must not overwrite them.
5. Refactor one owning module or adapter slice. Keep domain policy independent of pyelftools,
   SQLite, zstd, and CLI composition details.
6. Run the focused tests, `uv run just test-unit`, and `uv run just check`; then run the required
   `uv run just test` loop before moving to another slice.
7. At handoff, run coverage/audit gates and record external real-asset, Docker, or MSVC validation
   separately.

## Completion record

Every goal handoff should separate:

- confirmed facts, with the command or artifact that proves each one;
- approximate or producer-specific behavior that is intentionally bounded;
- tool authority, profile arguments, source/tool/output hashes, and cold/warm cache state;
- blocked checks and their exact missing prerequisite;
- remaining uncertainty, especially where original C++ behavior cannot be recovered from DWARF.

Budgets, elapsed time, or an incomplete implementation are not completion evidence. The goal is
complete only after the named verification surface passes or an explicit external prerequisite is
recorded as blocked for follow-up.

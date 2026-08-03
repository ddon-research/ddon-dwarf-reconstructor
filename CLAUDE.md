---
description: 'Claude adapter for the DDON DWARF reconstructor'
applyTo: '**/*'
---

# Claude project adapter

`AGENTS.md` is the canonical repository instruction source. The Python-specific rules in
`.github/instructions/python.instructions.md` apply to Python files; this file only supplies the
same tool loop for Claude-compatible clients. Markdown changes also follow
`.github/instructions/documentation.instructions.md` and the
[documentation style reference](docs/reference/documentation-style.md).

## Development loop

Use regular CPython 3.14.6 and the locked uv environment:

```text
uv sync --python 3.14.6
uv run just test-unit
uv run just test-integration
uv run just check
uv run just test
uv run just coverage-ci
uv run just audit
```

Use the unified root CLI:

```text
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol MtObject
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol MtObject --full-hierarchy
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbols-file resources/season2-resources.txt
uv run ddon-dwarf-reconstructor artifacts inspect --elf resources/DDOORBIS.elf
uv run ddon-dwarf-reconstructor artifacts inspect-elf <PS4-ELF>
uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-dump <LLVM-DWARF-DUMP.zst>
uv run ddon-dwarf-reconstructor artifacts list-tool-profiles
uv run ddon-dwarf-reconstructor artifacts probe-tool <tool> --output-dir output/tool-probes
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence <elf> \
  --tool <tool> --profile <profile> --output-dir output/tool-exports
uv run ddon-dwarf-reconstructor export-knowledge <elf> --symbol <name> \
  --output-dir output/knowledge --tool-evidence output/tool-exports/<key>/manifest.json
docker compose --file tools/binary_toolchain/compose.yaml config --quiet
```

The standalone specification tool is run from its own project boundary:

```text
uv run --directory tools/dwarf_spec_pipeline just check
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline validate \
  --output-dir ../../docs/knowledge-base/dwarf-specification/generated
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline audit \
  --output-dir ../../docs/knowledge-base/dwarf-specification/generated --source-root ../../src
```

## GitHub Actions and supply-chain loop

Read `.github/instructions/github-actions.instructions.md` and [validate changes](docs/how-to/validate-changes.md) for the
workflow contract. Hosted CI is an adapter over the local `just` recipes: quality runs `check`,
including actionlint, package smoke, and blocking `audit`; correctness runs `coverage-ci` with deterministic integration;
the nested workflow runs its own `just ci`. All action references are full-SHA pins with release
comments, and Dependabot owns discovery of new refs.

Use shallow credential-free checkout, lockfile-keyed uv caching, explicit timeouts, concurrency
cancellation, and least-privilege permissions. CodeQL and Dependency Review are free public-repo
integrations; Codecov is advisory. Do not use `pull_request_target` to execute contributor code,
upload proprietary inputs, log secrets, or treat remote Settings changes as completed by editing
the checkout. Capture read-only `gh` workflow, PR, action-release, and security-setting evidence
before changing CI.

## Engineering constraints

- Preserve immutable input identity, source-bound durable caches, atomic publication, deterministic
  ordering, qualified names, offsets, layouts, provenance, and generated-header bytes. Source
  identity fast keys use size, mtime, device, and inode; ctime drift is accepted only for a moved
  catalog path, and explicit verification performs the complete hash.
- Keep domain, application, and infrastructure boundaries intact. New CLI code belongs at the
  composition root and must convert into typed application requests.
- Do not commit ELF files, expanded dumps, generated headers, caches, logs, credentials, or real
  performance artifacts.
- Use explicit local paths for real PS4 and compiler validation; retain cold/warm state and record
  the manifest identity.
- Probe external tools before selecting an export profile. Orbis executables are authoritative for
  PS4 ABI/SCE semantics; LLVM, GNU Binutils, elfutils, libdwarf, pyelftools, LIEF, and OpenOrbis
  outputs are additive evidence. The `elfldr` reference is loader research only and is not run by
  the ingestion path.
- Update the README, the affected Zensical source pages, active contracts, and Spec Kit artifacts
  whenever public commands, configuration, or validation behavior changes. Keep Mermaid/UML
  diagrams in Markdown, use C4 context/container/component views plus native UML or runtime views
  at the smallest useful abstraction, keep one Diátaxis page intent per page, use the applicable
  arc42 sections for architecture, and run `uv run just docs-check` for Markdown, Mermaid, and
  strict site validation after `uv run just docs-tools-install` on a fresh checkout.
- Root tests use one scope (`unit`, `integration`, or `acceptance`) plus a purpose
  (`functional`, `regression`, or `non_functional`). Collection enforces the taxonomy; qualify
  performance, slow, real-asset, packaging, and quality work explicitly.
- The default `just test` and coverage loop includes deterministic integration tests. Use
  `just test-without-integration` only for exceptional iteration, and run the required loop before
  handoff. Real-asset and performance checks remain explicit local evidence.
- Profiling uses the canonical `performance` command group and the `performance-*` just recipes.
  `performance doctor` reports tool availability; `performance profile-index` measures a true
  compressed-dump rebuild separately; the typed runner samples an isolated process
  tree with psutil and publishes checksummed raw manifests outside Git; `performance history`
  writes the tracked SQLite/static exports. Scalene is primary, cProfile/pyinstrument/py-spy and
  tracemalloc are cross-checks, and pyperf is the repeated deterministic fixture harness. Never
  instrument normal generation or treat unavailable/partial real-asset evidence as green.

For a multi-turn DWARF investigation, use a thread-scoped Codex goal. Define the outcome and
evidence surface first, inspect the validated PS4 DWARF4/PS3 DWARF2 producer facts and semantic
index, then iterate through focused tests and the required gates. Separate confirmed facts from
approximation, blocked prerequisites, and remaining uncertainty before declaring completion.
For CI or Dependabot work, inspect gh auth status, gh pr diff, gh pr checks, and gh run view
<run-id> --log-failed before changing the local implementation. Passing quality checks do not
replace a failed correctness check.

## Observability loop

- Runtime modules use the standard-library facade in `core.observability`; `LoggerSetup` owns the
  structlog processor/rendering adapter. Keep domain code independent of structlog, Rich, and
  OpenTelemetry.
- Emit bounded structured events at stage boundaries, use context fields (`run_id`, symbol, source
  identity, and optional trace/span identifiers), and choose levels deliberately: info for progress,
  debug for bounded detail, warning for partial/recoverable evidence, and error for failed work.
- Use `exc_info` or `log_exception` and preserve chained causes with `raise ... from error`. Validate
  JSONL event fields and nested traceback records in focused tests; keep artifact JSON on stdout and
  diagnostics on stderr/log files.

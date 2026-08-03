---
description: 'Copilot adapter for the DDON DWARF reconstructor'
applyTo: '**/*'
---

# Copilot project adapter

`AGENTS.md` is the canonical repository instruction source for Codex and Copilot. The
path-specific Python rules in `.github/instructions/python.instructions.md` apply to every Python
file. This file contains only Copilot-facing project context and workflow reminders; it must not
contradict either source.

## Project constraints

- The project reconstructs deterministic C++ headers from very large PS4 ELF/DWARF inputs.
- Use regular CPython 3.14.6 and `uv`; install the development environment with
  `uv sync --python 3.14.6`.
- Treat inputs for a named DDON build as immutable. Preserve validated source-bound indexes and
  caches locally, and never commit ELF files, compressed dumps, generated headers, caches, logs, or
  credentials.
- Preserve qualified names, inheritance, field offsets, sizes, source locations, DIE/CU
  provenance, deterministic ordering, cache formats, and source offsets. Offset `0` is valid.
- Treat external tool output as a separate, source-bound evidence layer. Start with
  `artifacts list-tool-profiles` and explicit `probe-tool` help/version captures; publish named
  exports with `export-tool-evidence` and attach them to knowledge export with repeated
  `--tool-evidence`. Orbis is authoritative for PS4 ABI/SCE semantics; generic LLVM, GNU,
  elfutils, libdwarf, pyelftools, LIEF, and OpenOrbis results remain additive until validated.

## Architecture rules

Use the existing domain-driven and hexagonal structure:

- Domain code owns models, policies, and ports. It must not import SQLite, zstd, `pyelftools`,
  Orbis/process models, or concrete filesystem adapters.
- Application code coordinates use cases through typed ports and request/response contracts.
- Infrastructure implements adapters for ELF/DWARF, compressed dumps, SQLite, caches, disassembly,
  filesystem, and processes. Composition roots construct those adapters.
- Prefer typed contracts such as `GenerationRequest`, `HeaderBundle`, `DefinitionCandidate`, and
  structured type/declarator models. Breaking changes are acceptable when they remove unnecessary
  indirection; update in-repository callers and tests instead of preserving old import shapes.
- `ElfDwarfSession` owns ELF/DWARF lifetime and the single PS4 normalization boundary;
  `DwarfRuntimeConfig` owns validated cache/search settings; `SearchResult` owns lookup status and
  CU/DIE provenance; and `AtomicHeaderPublisher` owns generated-bundle publication and manifests.
- Reuse canonical policy services for definition selection, source identity, type classification,
  method evidence, special-header rendering, and array/declarator parsing. Do not add a second
  implementation in an alternate generator or adapter.

## Observability and exception handling

- Use `ddon_dwarf_reconstructor.core.observability` as the technology-neutral logging boundary.
  Emit stable snake_case events with `log_event`; use `bind_context` for `run_id`, command, input
  identity, symbol, stage, and future `trace_id`/`span_id` fields. Infrastructure configures
  structlog, JSONL files, and Rich stderr rendering; domain code must not import those libraries.
- Keep logs useful and bounded: info marks pipeline/stage progress, debug records cache/search
  detail, warning marks partial/unavailable evidence or recovery, and error marks failed operations.
  Never log every DIE, entire generated headers, binary contents, credentials, or unrestricted tool
  output. Keep artifact JSON on stdout; runtime diagnostics go to stderr and the log file.
- Catch the narrowest expected exception, attach `exc_info=error` or use `log_exception`, and keep
  exception chaining with `raise ... from error`. A diagnostic that only logs `str(error)` is not
  sufficient for debugging nested causes and source line references.
- Add or update focused tests for JSON field shape, callsite information, nested tracebacks,
  context reset, and failure-mode behavior whenever a critical path changes.

## Commands

Always use `uv run` for project Python commands and the packaged entry point for generation:

```text
uv run ddon-dwarf-reconstructor ...
uv run just test-unit
uv run just test-integration
uv run just test
uv run just check
uv run ddon-dwarf-reconstructor generate <elf> --symbol <name>
uv run ddon-dwarf-reconstructor artifacts inspect --dwarf-dump <path>
uv run ddon-dwarf-reconstructor artifacts inspect-elf <elf>
uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-dump <dump.zst>
uv run ddon-dwarf-reconstructor artifacts list-tool-profiles
uv run ddon-dwarf-reconstructor artifacts probe-tool <tool> --output-dir output/tool-probes
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence <elf> \
  --tool <tool> --profile <profile> --output-dir output/tool-exports
uv run ddon-dwarf-reconstructor export-knowledge <elf> --symbol <name> \
  --output-dir output/knowledge --tool-evidence output/tool-exports/<key>/manifest.json
docker compose --file tools/binary_toolchain/compose.yaml config --quiet
uv run --project tools/dwarf_spec_pipeline dwarf-spec-pipeline audit \
  --output-dir docs/knowledge-base/dwarf-specification/generated --source-root src
```

Before handoff, run `uv run just test`, `uv run just coverage-ci`, and `uv run just audit`.
`just check` and the CI workflows are the authoritative aggregations of these gates. Coverage
targets are at least 80% total lines, with at
least 80% lines and 70% branches in parsing, generation, orchestration, and artifact modules. Ruff,
Pyrefly, and deptry remain authoritative; Prospector is only for focused duplicate, dead-code,
import, complexity, and maintainability diagnostics.

## Regression and performance rules

- Compare generated `.h` and `.hpp` files byte-for-byte using
  `uv run python -m tests.support.regression.output_manifest`; do not replace header regression
  tests with snapshots.
- Every root test has exactly one scope marker (`unit`, `integration`, or `acceptance`) and at
  least one purpose marker (`functional`, `regression`, or `non_functional`). The collection hook
  rejects missing/ambiguous classifications. Mark `performance`, `slow`, `real_asset`,
  `packaging`, and `quality` qualifiers explicitly and satisfy their compatibility rules.
- Required deterministic integration tests are included in `uv run just test` and coverage. Use
  `uv run just test-without-integration` only as an exceptional fast iteration shortcut; it is not
  the handoff gate. Use `test-regression`, `test-non-functional`, `test-acceptance`,
  `test-real-assets`, and `test-performance` for explicit evidence slices.
- Validate the packaged entry point and each intentional output mode in fresh-process and warm-cache
  runs, and record input identity, producer/configuration identity, and cache state.
- Keep real-artifact baselines outside source control; commit only small deterministic manifests or
  structured expectations. Real PS4 runs are opt-in and require explicit local paths.
- The Compose image is a non-proprietary generic baseline only. Do not copy Sony SDKs into it;
  mount inputs read-only and preserve tool identity, command profile, output checksum, authority,
  and cache state in the export manifest.
- Stream compressed dumps in one pass with bounded memory. Avoid repeated ELF hashing, repeated
  full-DIE scans, unnecessary rescans, and unbounded intermediate collections. Cache artifacts must
  be source-bound, validated before reuse, and published atomically.

## Change workflow

- Inspect the current worktree and preserve unrelated edits.
- Put new code in the owning layer and mirror the package layout in `tests/`; put shared typed DIE
  builders and fixtures in `tests/support/`.
- Add focused tests for incomplete, conflicting, duplicate, unavailable, cyclic, malformed, and
  timeout evidence. Use Hypothesis for pure parser/type/declarator invariants and
  `pytest-regressions` only for small deterministic records.
- Keep every non-generated Python module under 600 lines, class under 500 lines, function/method
  under 75 lines, and McCabe complexity at or below 10. There are no baseline exemptions.
- Use specific exceptions and structured diagnostics. Do not add blanket `Any`, broad exception
  swallowing, truthiness checks for optional offsets, or unexplained architecture exemptions.
- Update affected README, architecture, generation-flow, testing, and Spec Kit artifacts. Record
  unresolved evidence or deferred prerequisites there rather than hiding them in code.

## Goal-oriented research workflow

For multi-step DWARF correctness work, use a thread-scoped Codex goal with an explicit outcome,
verification surface, constraints, boundaries, iteration action, and blocked condition. Start with
ELF/dump producer evidence and the generated DWARF semantic index; then make one parser/evidence
slice, run the focused tests and `just check`, and continue only from observed results. A goal is
complete only when its evidence surface passes. Report confirmed, approximate, blocked, and
remaining-uncertainty findings separately; do not treat a time or token budget as completion.

For repository-wide instructions, performance constraints, safety rules, and the complete
validation sequence, follow `AGENTS.md`.

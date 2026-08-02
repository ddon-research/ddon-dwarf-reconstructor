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

## Commands

Always use `uv run` for project Python commands and the packaged entry point for generation:

```text
uv run ddon-dwarf-reconstructor ...
uv run just test-unit
uv run just check
uv run ddon-dwarf-reconstructor generate <elf> --symbol <name>
uv run ddon-dwarf-reconstructor artifacts inspect --dwarf-dump <path>
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
- Validate the packaged entry point and each intentional output mode in fresh-process and warm-cache
  runs, and record input identity, producer/configuration identity, and cache state.
- Keep real-artifact baselines outside source control; commit only small deterministic manifests or
  structured expectations. Real PS4 runs are opt-in and require explicit local paths.
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
- Keep every non-generated Python module under 400 lines, class under 250 lines, function/method
  under 75 lines, and McCabe complexity at or below 10. There are no baseline exemptions.
- Use specific exceptions and structured diagnostics. Do not add blanket `Any`, broad exception
  swallowing, truthiness checks for optional offsets, or unexplained architecture exemptions.
- Update affected README, architecture, generation-flow, testing, and Spec Kit artifacts. Record
  unresolved evidence or deferred prerequisites there rather than hiding them in code.

For repository-wide instructions, performance constraints, safety rules, and the complete
validation sequence, follow `AGENTS.md`.

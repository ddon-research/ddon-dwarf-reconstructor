---
description: 'Python design, maintainability, testing, and architecture rules for this repository'
applyTo: '**/*.py'
---

# Python instructions

These rules supplement the repository-wide `AGENTS.md`. Use regular CPython 3.14.6 through `uv`;
do not bypass the managed environment with bare `pytest`, `python -m pytest`, or ad-hoc imports
through the repository's `src` directory.

## Design and typing

- Use package-relative imports and complete annotations for parameters, return values, attributes,
  and public protocols. Keep the configured Pyrefly project clean at warning severity; prefer
  `X | None` over `Optional[X]`.
- Keep domain code independent of infrastructure. Domain modules may use domain models, ports,
  policies, and the standard library; application modules coordinate use cases; infrastructure
  modules implement external adapters. Only composition roots instantiate concrete adapters.
- Use small immutable or deliberately-owned typed models for cross-layer data. Prefer existing
  `GenerationRequest`, `HeaderBundle`, `DefinitionCandidate`, type-reference, and declarator
  contracts over untyped dictionaries or repeated parameter lists.
- Breaking changes are allowed when they remove unnecessary indirection. Update in-repository
  callers, tests, and contracts atomically; do not add a wrapper just to avoid changing a caller.
- Keep one policy implementation for definition selection, source identity, primitive/excluded-type
  classification, method evidence, special-header rendering, and array/declarator parsing.
- `DwarfRuntimeConfig.from_environment()` is the only source for runtime cache sizes and search
  bounds. Invalid `DWARF_DIE_CACHE_SIZE`, `DWARF_TYPE_CACHE_SIZE`, or
  `DWARF_MAX_SEARCH_TIME_MS` values are configuration errors, not reasons to silently use defaults.
- `ElfDwarfSession` owns ELF/DWARF handles and PS4 pyelftools normalization. Do not open ELF files
  or invoke the patch installer from domain services or individual generators.
- `SearchResult` carries status, candidate score, CU/DIE provenance, elapsed time, and diagnostics.
  Callers must make an explicit decision about partial or unavailable evidence.
- `AtomicHeaderPublisher` is the sole generated-header writer. Stage a complete bundle, publish its
  manifest, and preserve rollback behavior; do not add a second content cache or direct writes.
- Use explicit `is not None` checks for optional numeric evidence. Offset `0` is valid.
- Catch specific expected exceptions, preserve useful context, and emit structured diagnostics.
  Do not use bare `except`, unexplained `Any`, or silent fallbacks.

## Logging and exception diagnostics

- Use `get_logger`, `log_event`, `log_exception`, and `bind_context` from
  `core.observability`; keep the core/domain boundary on `logging.Logger` so the infrastructure
  renderer can evolve toward OpenTelemetry without third-party imports in policy code.
- Use stable snake_case event names and bounded JSON-compatible fields. Record stage boundaries and
  durations at info/debug levels, preserve partial/unavailable evidence as warnings, and reserve
  errors for failed operations. Do not emit per-DIE/per-line logs or full input/output objects.
- Pass caught exceptions through `exc_info=error` or `log_exception` so chained exceptions retain
  frames, line numbers, and causes. When translating errors, use `raise NewError(...) from error`;
  do not swallow unexpected failures or replace tracebacks with an error string.
- Context fields such as `run_id`, `symbol`, source identity, and future `trace_id`/`span_id` must
  be scoped with `bind_context` and reset after the operation. Extend the focused logging tests when
  event fields or exception behavior changes.

## CLI and dependency boundaries

- Keep Typer handlers at the composition boundary. Convert CLI values into typed application
  requests; do not import Typer or Click into domain or infrastructure policy code.
- Use the unified root command tree (`generate`, `export-knowledge`, `artifacts`) and the nested
  `dwarf-spec-pipeline` command tree. Repeat `--symbol` for multiple symbols; do not reintroduce
  comma-separated parsing.
- Declare runtime dependencies in `[project.dependencies]` and development tools in PEP 735
  `[dependency-groups]`. Run tools through `uv run`; use `deptry` to detect missing or misplaced
  dependencies and keep module-name mappings explicit for packages such as `pyelftools`.
- The committed Pyrefly configuration is explicit and authoritative. If a new checkout has no
  `[tool.pyrefly]` section, run `uv run pyrefly init pyproject.toml` once, then review and commit
  the explicit configuration; do not add a second type-checker configuration or broad
  missing-import suppression.

## Size and complexity gates

All non-generated Python under `src/` and `tests/` must satisfy these hard limits:

- module: at most 400 physical lines;
- class: at most 250 physical lines;
- function or method: at most 75 physical lines;
- McCabe complexity: at most 10.

When a limit is approached, extract a cohesive service, renderer, policy, port, or test fixture.
Do not suppress the checker or add a baseline exemption.

## Testing and validation

- Mirror the production package layout in `tests/`; place shared typed DIE builders and fixtures in
  `tests/support/`.
- Mark fast isolated tests `unit`; reserve `integration`, `slow`, and `performance` for tests
  that need the corresponding resources.
- Use Hypothesis for pure type-reference, declarator, array, qualifier, pointer, and parser
  invariants. Use `pytest-regressions` only for small deterministic diagnostics and metadata.
- Exercise missing, incomplete, conflicting, duplicate, unavailable, cyclic, malformed, and
  timeout evidence, plus stale caches, interrupted atomic writes, lock behavior, warm lookups, and
  offset `0` cases where relevant.
- Compare generated `.h`/`.hpp` files byte-for-byte with the output-manifest helper.

The normal loop is:

```text
uv run just test-unit
uv run just check
uv run just test
uv run just coverage-ci
uv run just audit
```

For real PS4 or performance validation, use explicit local input and index paths, retain cold and
warm state, and store generated artifacts outside source control. Update the relevant Spec Kit and
documentation artifacts with the exact command and evidence.

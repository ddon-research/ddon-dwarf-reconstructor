# Implementation Plan: Source-backed documentation platform

## Baseline evidence

- The initial inventory found 272 Python files and 94 Markdown files; the then-current
  the former monolithic architecture page was 1,625 lines and was the main source of overlap. That
  legacy page is now retired in favor of the navigated architecture explanations.
- The runtime exposes `generate`, `export-knowledge`, and `artifacts`; the graph exporter writes
  deterministic JSONL and manifests, not a live database.
- The root and `tools/dwarf_spec_pipeline` projects have independent uv boundaries. The canonical
  nested invocation is `uv run --directory tools/dwarf_spec_pipeline ...`.
- The existing code and tests implement PS3 `DW_OP_plus_uconst`/`DW_OP_constu` location decoding,
  source-bound caches, atomic header publication, and explicit evidence statuses.

## Design

1. Add root Zensical configuration with explicit Diátaxis navigation and Mermaid superfences.
2. Write compact source-backed pages for tutorials, how-to tasks, arc42 architecture, low-level
   type resolution, stable CLI/artifact/testing contracts, the graph boundary, and roadmap.
3. Retain research and generated DWARF specification artifacts in the knowledge base, but retire
   stale duplicate narratives and update their canonical command links.
4. Add `zensical` to the root docs dependency group and make strict site build part of `just check`.
5. Add a SHA-pinned GitHub Pages workflow using the local uv setup action.
6. Synchronize README and all instruction adapters with the new paths, evidence rules, and tooling.

## Files

- Site: `zensical.toml`, `docs/index.md`, `docs/tutorials/`, `docs/how-to/`, `docs/explanation/`,
  `docs/reference/`, `docs/roadmap/`.
- Tooling: `pyproject.toml`, `uv.lock`, `justfile`, `.github/workflows/docs.yml`.
- Guidance: `README.md`, `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`,
  `.github/instructions/python.instructions.md`, `.github/instructions/github-actions.instructions.md`,
  `tests/README.md`, `tools/dwarf_spec_pipeline/README.md`.
- Roadmap: `specs/012-documentation-platform/`.

## Validation tiers

- Focused: `uv run just docs-build`; inspect generated site and Mermaid pages.
- Root fast: `uv run just test-unit`, `uv run just check`, `uv run just test`.
- Handoff: `uv run just coverage-ci`, `uv run just audit`, package smoke as applicable.
- Nested: `uv run --directory tools/dwarf_spec_pipeline just test`, `test-official`, and `check`.
- External: GitHub Pages activation and deployment are remote evidence checked after the local
  build; record the configured URL and workflow result separately from local acceptance evidence.

## Final validation evidence

- `uv run just docs-build`: passed; Zensical 0.0.52 strict build reported no issues.
- `uv run just test-unit`: 445 passed, 6 deselected.
- `uv run just check`: passed with actionlint v1.7.12 available through the current shell's WinGet
  link; the repository does not add a custom PATH guard.
- `uv run just test`: 447 passed, 4 deselected.
- `uv run just coverage-ci`: 84.87% total coverage; named high-risk groups met their line/branch
  thresholds.
- `uv run just audit`: Prospector completed with zero messages.
- `uv run just package` and `uv run just package-smoke`: passed.
- Nested `just test`, `just test-official`, `just check`, and `uv lock --check`: passed; the
  official selection skipped one test because `DWARF_SPEC_OFFICIAL=1` requires a prior Docker
  Compose build.
- The pre-existing `ideas.md` edit and `resources/.cache/` local acceptance index were preserved.
- Zensical `--clean` is intentionally not part of the repository recipe because it clears the
  project `.cache`, which contains durable source-bound DWARF artifacts.

# Feature specification: exhaustive Python API reference

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

**Feature branch:** `020-documentation-api-reference`  
**Status:** Implemented and locally acceptance-verified on 2026-08-16  
**Owner:** DDON DWARF Reconstructor maintainers

## Intent

Add an exhaustive, source-derived Python module reference to the existing Zensical site. The
reference is intended for maintainers and developers who need signatures, annotations, docstrings,
and implementation contracts. It indexes every source module, including infrastructure and parser
internals, but does not claim that every indexed module or member is a stable public API.

## Requirements

- **API-020-1:** The `docs` dependency group MUST include
  `mkdocstrings-python>=2.0,<3`, and `uv.lock` MUST retain the exact validated dependency
  resolution with the existing Zensical version.
- **API-020-2:** Zensical MUST configure the Python handler with `paths = ["src"]`, the Python
  standard-library inventory, Google-style docstrings, inherited members, source display disabled,
  source-derived member ordering, and rendered root headings.
- **API-020-3:** The existing sidebar TOC MUST use the title `On this page`, depth three, accessible
  permalink text, and `toc.follow`; authored pages MUST NOT add an in-page TOC marker.
- **API-020-4:** The generator MUST discover every `.py` file under
  `src/ddon_dwarf_reconstructor`, map `__init__.py` paths to package identifiers, order modules
  deterministically, and emit one `:::` directive per module in fixed root/application/core/domain/
  infrastructure/utilities pages.
- **API-020-5:** The generator MUST use no package imports and produce no HTML. `--check` MUST fail
  on missing, stale, duplicate, or unexpectedly grouped output.
- **API-020-6:** Zensical navigation MUST expose the API landing page and every generated group page;
  `docs-build` and `docs-check` MUST enforce the generated-page check before the strict build.
- **API-020-7:** The strict build MUST fail on an unresolved module directive or handler
  incompatibility. The implementation MUST NOT declare or configure `autorefs` or
  `mkdocs-gen-files` as separate plugins, nor introduce Sphinx, pdoc, or a second API
  documentation system as a fallback.
- **API-020-8:** README, documentation explanations/how-tos/style contract, contributor
  instructions, roadmap, and this feature record MUST describe the generated-page workflow and its
  evidence boundary.

## Evidence boundary

Current module inventory comes from the checked-in source tree and the deterministic generator.
Rendered API output and strict-build compatibility are local site evidence. Public API stability,
external backlink behavior, and remote GitHub Pages availability are not inferred from the module
inventory; Zensical's mkdocstrings support is preliminary and unsupported backlink behavior is not
part of this feature contract.

## Validation evidence

Observed on the Windows development host with CPython 3.14.7 and the locked uv environment:

- `uv sync --locked` and `uv lock --check` passed.
- `uv run just docs-api-check` found 305 modules in six generated pages.
- The focused generator suite passed all six tests.
- `uv run just docs-check` passed Markdownlint, 17 Mermaid diagrams across 68 Markdown files, and
  the strict Zensical build with no issues.
- `uv run just check` passed Ruff, formatting, actionlint, Pyrefly, deptry, structure, architecture,
  the generated-page check, documentation validators, and the strict build.
- `uv run just test-unit` passed 870 tests with seven explicit qualifiers deselected; `uv run just
  test` passed 872 tests with five explicit qualifiers deselected.
- `uv run just coverage-ci` passed the 80% gate and the repository coverage report (80.44% total
  line coverage; parsing, generation, orchestration, and artifact thresholds passed).
- `uv run just audit` passed Prospector with zero messages.

Rendered `site/api/generated/` pages contain module headings, annotated signatures, permalink
anchors, and the `On this page` sidebar TOC. No unresolved `:::` directive or strict-build warning
was observed. Public GitHub Pages publication remains outside this local evidence.

## Non-goals

- Declaring every implementation module a supported external API.
- Adding a second documentation generator, standalone API site, in-page TOC, or unsupported Zensical
  plugin.
- Changing application behavior beyond the package marker needed for Griffe to collect the existing
  `domain/ports` source group.

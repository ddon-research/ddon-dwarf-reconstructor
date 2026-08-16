# Tasks

- [x] T001 Inventory the dirty worktree, source package layout, Zensical configuration, Pages
  workflow, dependency groups, docs instructions, and test taxonomy.
- [x] T002 Add `mkdocstrings-python>=2.0,<3` to the `docs` group, update `uv.lock`, configure the
  Python handler, and extend the existing TOC/sidebar settings.
- [x] T003 Add the `domain/ports` package marker required for the locked Griffe handler to collect
  the existing namespace-only source group without omitting its modules.
- [x] T004 Implement the deterministic API generator and focused taxonomy-compliant tests for
  discovery, package conversion, ordering, duplicate detection, stale output, and unexpected
  groups.
- [x] T005 Generate six fixed API group pages, add the landing page and explicit Zensical navigation,
  and verify every source module has exactly one directive.
- [x] T006 Add `docs-api` and `docs-api-check`; make the strict docs build enforce the generated-page
  check while preserving the existing Pages workflow shape.
- [x] T007 Synchronize README, docs explanations/how-tos/style, documentation tooling notes,
  contributor instructions, roadmap, and feature artifacts.
- [x] T008 Run the complete handoff validation loop: `uv sync --locked`, `uv lock --check`,
  `docs-api-check`, `docs-check`, `check`, `test-unit`, `test`, `coverage-ci`, and `audit`; record
  any environmental or repository blockers explicitly.

## Deferred or blocked evidence

- Public GitHub Pages deployment and unsupported mkdocstrings backlinks are outside the local build
  evidence. The existing Pages workflow remains the publication mechanism and must not be treated
  as verified until its normal remote run publishes the changed site.

# Tasks: Source-backed documentation platform

## Inventory and design

- [x] T001 Scan source layers, CLI surfaces, test taxonomy, existing docs, instructions, specs,
  workflows, and worktree state; preserve unrelated edits.
- [x] T002 Define the Zensical, Diátaxis, arc42, Mermaid/UML, knowledge-graph, and roadmap source
  boundaries in `docs/explanation/documentation-system.md`.
- [x] T003 Record the current graph contract and missing live-ingestion capability.

## Site implementation

- [x] T004 Add `zensical.toml` with explicit navigation and Mermaid superfences.
- [x] T005 Add tutorial, how-to, architecture, low-level explanation, reference, and roadmap pages
  from current source behavior.
- [x] T006 Add Mermaid flowchart, sequence/state, ER, and UML class diagrams as Markdown source.
- [x] T007 Build the site from a fresh locked environment and repair all strict-build issues.

## Migration and tooling

- [x] T008 Add the root docs dependency group and `docs-serve`/strict `docs-build` recipes.
- [x] T009 Add the SHA-pinned GitHub Pages workflow and keep permissions deployment-specific.
- [x] T010 Update README, AGENTS, Copilot, Claude, Python, GitHub Actions, test, and nested-tool
  guidance to the new paths and `--directory` boundary.
- [x] T011 Remove or rewrite all obsolete duplicate pages and stale internal documentation links.
- [x] T012 Update the feature status and roadmap after final validation evidence.

## Handoff validation

- [x] T013 Run root focused/fast/handoff gates and record failures or external blockers.
- [x] T014 Run nested project validation and inspect the final diff for unrelated changes.
- [x] T015 Complete the goal only after the named evidence surface passes; otherwise retain the
  concrete blocker in this feature record.

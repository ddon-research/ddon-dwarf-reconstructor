# Tasks: Documentation style and governance

## Research and contract

- [x] T001 Review the cited arc42, Diátaxis, INNOQ, and Awesome Copilot guidance and record the
  synthesis in `spec.md` and `plan.md`.
- [x] T002 Define the project tone, page taxonomy, evidence vocabulary, arc42 mapping, diagram
  policy, and review loop in `docs/reference/documentation-style.md`.
- [x] T003 Add the reusable Markdown instruction and documentation-writer skill.

## Documentation refactor

- [x] T004 Add `docs/how-to/write-documentation.md` and add it to `zensical.toml`.
- [x] T005 Refactor the documentation-system explanation and goal workflow around the new contract.
- [x] T006 Refactor the architecture index, roadmap, knowledge-graph boundary, and validation guide
  to show current evidence and deferred work without duplicate narratives.
- [x] T007 Synchronize README, AGENTS, Copilot, Claude, Python, and GitHub Actions guidance.

## Validation

- [x] T008 Build the strict Zensical site and run the root quality loop.
- [x] T009 Inspect the final diff and preserve unrelated worktree edits and durable local evidence.

## Deferred knowledge-graph task

- [ ] KG-001 Define and implement a versioned loader over the existing JSONL bundle with
  deterministic query fixtures, provenance-preserving authority rules, LadybugDB-first compatibility
  evidence, and acceptance evidence. The authoritative task record is the [KG-001 feature
  record](../015-ladybugdb-knowledge-graph/tasks.md); do not start live LadybugDB/API/browser
  integration until that contract is verified.

# Tasks: Source-bound profiling and benchmark history

## Contracts and runner

- [x] T001 Add typed workload, metric, method-summary, artifact, tool, and run contracts.
- [x] T002 Add isolated process-tree sampling, bounded output capture, timeout termination, and
  atomic raw-artifact manifests.
- [x] T003 Add Scalene, cProfile, pyinstrument, py-spy, tracemalloc, and pyperf adapters with
  explicit unavailable/partial evidence.
- [x] T004 Retire the unreferenced `ProgressTracker` timing/memory path.

## History and commands

- [x] T005 Add the versioned SQLite v1 schema and typed metric/method/artifact persistence.
- [x] T006 Add deterministic JSON, CSV, and Markdown history exports and like-for-like compare.
- [x] T007 Add `performance doctor`, `profile`, `benchmark`, `history compare`, and
  `history export` to the canonical Typer tree.
- [x] T008 Add explicit just recipes for tool installation, fixture/real performance, profiling,
  and history export.

## Tests and evidence

- [x] T009 Add contract, workload-construction, runner, timeout, history, export, and deterministic
  fixture tests.
- [x] T010 Refactor the real `rLayout` budget onto the common runner and current CLI tree.
- [x] T011 Run the warm real `rLayout` cross-check with local ELF/index paths and retain external
  manifests; record unavailable profiler permissions explicitly.
- [x] T012 Run cold compressed-dump index construction separately and record its resource evidence.

## Documentation and convergence

- [x] T013 Update README, validation/testing references, architecture crosscutting concepts,
  navigation, roadmap, goal workflow, and knowledge-base index.
- [x] T014 Synchronize AGENTS, Copilot, Python, and Claude adapter instructions.
- [x] T015 Run the required root validation and nested project checks; retain failures and external
  prerequisites in `measured-evidence.md`.

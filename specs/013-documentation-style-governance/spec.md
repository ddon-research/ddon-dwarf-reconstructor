# Feature Specification: Documentation style and governance

**Feature branch:** `013-documentation-style-governance`
**Status:** Style contract implemented; LadybugDB-first `KG-001` remains explicitly deferred
**Owner:** DDON DWARF Reconstructor maintainers

## Problem

The repository now has a Zensical site with Diátaxis navigation and arc42 architecture pages, but
the writing contract is distributed across several adapters. Without a single tone, evidence, page
intent, and review rule, new pages can reintroduce mixed-purpose narratives, unsupported claims, or
obsolete duplicates. The next knowledge-graph integration also needs to remain a roadmap task
while the documentation governance work settles; its dedicated contract is maintained in the
[KG-001 feature record](../015-ladybugdb-knowledge-graph/spec.md).

## Outcome

The repository shall provide one reusable documentation contract for Codex, Copilot, Claude,
Python contributors, and documentation-specific automation. The contract shall make Diátaxis page
intent, arc42 architecture structure, source-backed evidence, Mermaid/UML diagrams, tone, and
validation mandatory for authored documentation while preserving the existing JSONL graph boundary.

## Requirements

- **STYLE-001:** Every authored page MUST have one primary Diátaxis intent and a clear audience,
  outcome, scope, and evidence boundary.
- **STYLE-002:** Architecture explanation MUST use the applicable arc42 compartments, top-down
  progressive disclosure, explicit decisions, and visible risks/deferred work.
- **STYLE-003:** The project voice MUST be direct, active, precise, source-backed, and explicit
  about uncertainty; reference pages MUST remain factual and how-to pages MUST remain task-focused.
- **STYLE-004:** Current behavior, intended behavior, external observations, approximations,
  deferred work, and blocked prerequisites MUST use distinct status and authority language.
- **STYLE-005:** Structural and runtime diagrams MUST remain Mermaid source in Markdown, use the
  smallest suitable standard or UML notation, and be explained by nearby text or tables. C4
  context/container/component views MAY be used for progressive architecture abstraction, with a
  native Mermaid fallback when experimental C4 syntax does not answer the reader's question.
- **STYLE-006:** The reusable contract MUST be available through the documentation path instruction,
  the documentation-writer skill, and synchronized repository adapters.
- **STYLE-007:** Documentation changes MUST validate the strict Zensical build and update navigation,
  specs, roadmap, and contributor guidance when the public contract changes.
- **STYLE-008:** `KG-001` MUST track the versioned JSONL graph loader, LadybugDB-first compatibility
  gate, provenance rules, and deterministic query fixtures; this feature MUST NOT implement a live
  LadybugDB database, API, or browser.

## Acceptance scenarios

1. A contributor can choose a page type and follow the authoring loop from the local style guide
   and how-to page without relying on an external writing framework.
2. The instruction adapters point to one tone, evidence vocabulary, arc42 mapping, diagram policy,
   and validation loop.
3. Existing authored site entry points use concise, direct, source-backed language and do not claim
   that the deferred graph integration exists.
4. `uv run just docs-build` and `uv run just check` validate the changed documentation surface.
5. The roadmap and the dedicated `KG-001` feature task list show the LadybugDB-first graph loader
   as an unchecked deferred task.

## Non-goals

- Implementing LadybugDB, a graph loader, graph queries, a graph API, or an interactive graph
  browser.
- Rewriting generated DWARF specification artifacts or changing reconstruction behavior.
- Introducing a second documentation generator, proprietary diagram format, or exported diagram
  image as the source of truth.
- Requiring a contributor to ask a clarification question when repository evidence supports a safe,
  explicit assumption.

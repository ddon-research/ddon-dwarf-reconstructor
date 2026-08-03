---
name: documentation-writer
description: 'Create and maintain source-backed DDON documentation using Diátaxis page intent and arc42 architecture structure.'
---

# DDON documentation writer

Use this skill for any non-trivial documentation change in the repository. It is an authoring
workflow, not a request to generate a generic project summary or a second source of truth.

## Preflight

1. Read `AGENTS.md`, `.github/instructions/documentation.instructions.md`, and the
   [documentation style reference](../../docs/reference/documentation-style.md).
2. Inspect the current page, its navigation entry, the implementation, focused tests, and the
   active Spec Kit feature. Preserve unrelated worktree changes.
3. Classify the page as tutorial, how-to, reference, explanation, or research note. Record the
   reader, goal, scope, prerequisites, and evidence boundary before drafting.

## Authoring loop

1. Write the smallest outline that serves the selected reader need.
2. Replace stale prose with source-backed claims. Link to the canonical code, test, contract,
   manifest, or external source instead of duplicating it.
3. Keep tutorials on one successful learning path, how-to guides on one concrete problem,
   references factual and searchable, and explanations focused on context, reasons, and trade-offs.
4. For architecture, map the page to the relevant arc42 compartment. Use C4 context/container/
   component diagrams for progressive abstraction levels and native Mermaid UML or runtime diagrams
   for code-specific questions. Explain every important relationship in nearby text; C4 syntax is
   experimental, so retain a native fallback when needed.
5. Mark implementation status and uncertainty. Add the next validation step for deferred or
   blocked work; do not imply that a future graph integration exists.
6. Update navigation, the README, the roadmap/spec, and instruction adapters when the contract or
   workflow changes. Remove obsolete duplicates.
7. Run `uv run just docs-tools-install` after checkout or a lockfile change, then run
   `uv run just docs-check`, `uv run just check`, and the relevant tests. Report skipped
   real-asset, compiler, remote, or performance evidence separately.

## Review gate

Reject a page that has no clear reader goal, mixes Diátaxis purposes without links, makes an
uncited implementation claim, hides uncertainty, duplicates a maintained contract, or contains an
unverified command. Prefer a shorter page that remains current over a comprehensive page that no
one can maintain.

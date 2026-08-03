# Write or update documentation

Use this guide when a code, workflow, investigation, or specification change needs documentation.
It produces one focused, source-backed page and keeps the static site, roadmap, and instruction
adapters aligned.

## 1. Select the page contract

Start with the reader's need:

| If the reader needs to... | Write a... |
| --- | --- |
| Learn by following one successful path | [Tutorial](../tutorials/first-generation.md) |
| Solve a known operational problem | How-to guide |
| Look up an exact command, option, artifact, or schema | Reference page |
| Understand context, reasons, architecture, or trade-offs | Explanation page |
| Revalidate an external or exploratory finding | Knowledge-base note |

Write the audience, outcome, scope, prerequisites, and evidence boundary in the opening paragraph.
If the page would serve two different needs, split it and link the pages.

## 2. Inspect before drafting

Read these in order:

1. `AGENTS.md` and `.github/instructions/documentation.instructions.md`.
2. The current page and its `zensical.toml` navigation entry.
3. The implementation and focused tests that define current behavior.
4. The active `specs/<feature>/` record for intent, tasks, and validation.
5. The relevant knowledge-base note or external source for research evidence.

For current behavior, source and tests outrank stale prose. For intended behavior, the active spec
outranks an unimplemented page. Record assumptions instead of silently filling evidence gaps.

## 3. Draft the smallest useful outline

Use the following shapes:

- **Tutorial:** outcome, prerequisites, one path, step-by-step commands, expected result after each
  meaningful step, and a short next step.
- **How-to:** problem, prerequisites, decision or input assumptions, procedure, verification,
  troubleshooting, and links to explanation/reference pages.
- **Reference:** purpose, scope, syntax or contract, fields/options, invariants, errors, and
  examples that clarify the contract without teaching it.
- **Explanation:** context, mental model, solution strategy, architecture or trade-offs, evidence,
  risks, and links to task/reference pages.
- **Knowledge-base note:** question, sources, authority, observations, interpretation, uncertainty,
  and next validation step.

Architecture explanations use the relevant arc42 compartments. They do not need to fill every
section, but they must make omitted or deferred concerns visible.

## 4. Write from evidence

Use exact repository paths and commands. Mark claims with the vocabulary from the
[documentation style reference](../reference/documentation-style.md): `Implemented`, `Verified`,
`Observed`, `Approximate`, `Deferred`, or `Blocked`.

For a diagram, keep Mermaid source in the page, choose one question, label relationships, and add
nearby prose or a table. Use `C4Context`, `C4Container`, and `C4Component` only at the abstraction
level that adds information; use `classDiagram` for UML structure and sequence/state diagrams for
runtime behavior. Mermaid C4 is experimental, so retain a native Mermaid fallback when it gives a
more stable or precise view. A diagram is evidence only when it matches the source and its scope is
stated.

## 5. Synchronize the repository

When the change affects a public workflow or contract, update the smallest affected set:

- `zensical.toml` navigation and the relevant `docs/` page;
- `README.md` when the entry point or contributor workflow changes;
- the active Spec Kit feature and `docs/roadmap/index.md`;
- `AGENTS.md`, `.github/copilot-instructions.md`, `CLAUDE.md`, or path-specific instructions when
  the authoring or validation contract changes.

Do not implement a future knowledge-graph integration while documenting its boundary. Track it as
an unchecked spec task with a named next step and acceptance evidence.

## 6. Validate and retire

Run the site build and repository gate:

```powershell
uv run just docs-tools-install  # once after checkout or lockfile changes
uv run just docs-check
uv run just check
```

Run focused tests when the page describes a changed contract. Use the nested project boundary for
specification-pipeline commands. Review links, code fences, headings, diagram semantics, and exact
paths. Remove obsolete duplicate pages and stale links rather than preserving parallel narratives;
Git provides the historical record.

## Documentation change goal

For a multi-turn documentation refactor, use this goal shape:

```text
Outcome: one source-backed page or documentation contract is complete.
Evidence: changed files, source/tests/spec links, docs-check, and applicable gates.
Constraints: preserve code behavior, generated evidence, stable commands, and unrelated edits.
Boundary: name excluded integrations, real assets, remote settings, or future work.
Iteration: research -> inventory -> outline -> write -> review -> validate -> retire.
Blocker: name the external prerequisite and the repeated check that would unblock it.
```

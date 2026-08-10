---
description: 'Source-backed documentation authoring rules for the DDON DWARF reconstructor'
applyTo: '**/*.md'
---

# Documentation authoring instructions

These rules supplement `AGENTS.md` whenever you create or edit Markdown. The reusable
[documentation style reference](../../docs/reference/documentation-style.md) defines the full
contract; the [documentation writer skill](../skills/documentation-writer/SKILL.md) provides the
repeatable authoring loop. Keep this adapter short enough to apply to every page.

## Choose the reader's need first

- Classify every authored page as a Diátaxis tutorial, how-to guide, reference, or explanation
  before writing it. State the audience, outcome, scope, and prerequisites in the opening prose.
- Keep one page focused on one reader need. Link to another page when the reader needs a different
  kind of content instead of combining a lesson, recipe, contract, and essay.
- Treat architecture pages as explanation pages organized with the relevant arc42 sections. The
  twelve sections are optional compartments; an empty or deferred compartment is more honest than
  invented detail.
- Treat knowledge-base notes as evidence records, not current contracts. Link them to the current
  reference or explanation page and preserve authority, source, status, and next validation step.

## Use the project voice

- Write in a calm, direct, objective, source-backed tone. Prefer active voice, present tense,
  concrete nouns, short paragraphs, and one main idea per paragraph.
- Start with the reader's task or question. Use direct address (`you`) in tutorials and how-to
  guides; use neutral project language in reference and architecture pages.
- Define an acronym or project-specific term on first use. Use the repository's established names,
  exact paths, commands, option names, and status vocabulary.
- Prefer a precise limitation to a vague promise. Avoid marketing language, filler, unexplained
  “simply” or “obviously,” rhetorical claims, and unqualified words such as “always” or “never.”
  Use an explicit prohibition when it protects data, evidence, or security.
- Do not copy source code or generated specifications into prose. Summarize the behavior, link to
  the authoritative path, and let tests or manifests carry exact detail.

## Preserve evidence and uncertainty

- For current behavior, inspect the implementation and tests first. For intended behavior, cite the
  active Spec Kit feature. For research, cite the external source and label the authority boundary.
- Mark claims as `Implemented`, `Verified`, `Observed`, `Approximate`, `Deferred`, or `Blocked`
  when that distinction affects a reader's decision. Include the evidence path or command and the
  next validation step for `Approximate`, `Deferred`, and `Blocked` claims.
- Never turn a deterministic producer fact into an inference. Keep `not_observed`, partial,
  conflicting, unavailable, and real-asset evidence visible.
- Remove an obsolete authored narrative once its useful content is represented elsewhere. Git
  history preserves the old version; parallel pages create drift.

## Write and model architecture deliberately

- Use top-down progressive disclosure: purpose and context, constraints and strategy, building
  blocks, runtime, deployment, cross-cutting concepts, decisions, quality, risks, and glossary.
- Name the responsibility and source location of important building blocks. Explain why a white-box
  decomposition exists and which runtime scenario proves its interaction.
- Keep Mermaid diagrams as fenced source in Markdown. Use `C4Context`, `C4Container`, and
  `C4Component` for architecture abstraction levels; use flowcharts for pipelines, `sequenceDiagram`
  or `stateDiagram-v2` for behavior, and `classDiagram` for UML structure.
- Give each diagram one question and one abstraction level to answer. Use stable IDs, quote labels
  containing punctuation, label relationships, and follow the diagram with prose or a table that
  explains important elements. Mermaid C4 is experimental, so keep a native fallback when C4 does
  not express the question clearly. Do not add decorative or source-generated diagrams without a
  maintenance owner.

## Verify before handoff

- Verify every command against the current CLI or `justfile`. Nested specification commands run
  from their own boundary with `uv run --directory tools/dwarf_spec_pipeline ...`.
- Update `zensical.toml` navigation, the relevant README, Spec Kit feature, roadmap entry, and
  instruction adapter when a public workflow or documentation contract changes.
- Run `uv run just docs-tools-install` after checkout or a documentation-tool lockfile change,
  then run `uv run just docs-check` for every site change and `uv run just check` before handoff.
  Run focused tests and the nested project's checks when the changed page describes those
  contracts.
- Review internal links, headings, code fences, diagram semantics, source paths, dates, version
  claims, and obsolete duplicate pages. Preserve unrelated worktree edits and local evidence.

# Implementation Plan: Documentation style and governance

## Research synthesis

- Arc42 provides twelve optional architecture compartments, a top-down reading order, practical
  stakeholder and quality guidance, and a docs-as-code model that fits Markdown in Git.
- Diátaxis separates learning, task completion, lookup, and understanding. The separation is a
  boundary against mixed-purpose pages, not a reason to duplicate content.
- Technical-writing guidance reinforces correctness, currency, relevance, referenceability,
  maintainability, findability, version control, active language, source-controlled diagrams, and
  continuous updates.
- The local contract adapts those principles to deterministic evidence: source and tests define
  current behavior, specs define intent, research notes preserve bounded observations, and deferred
  graph work remains visible.

## Research sources

- [INNOQ: Principles of technical documentation](https://www.innoq.com/en/blog/2022/01/principles-of-technical-documentation/)
- [arc42: Documentation](https://arc42.org/documentation/)
- [arc42 documentation home](https://docs.arc42.org/home/)
- [arc42 keyword index](https://docs.arc42.org/keywords/)
- [arc42 FAQ](https://faq.arc42.org/home/)
- [INNOQ: Brief introduction to arc42](https://www.innoq.com/en/blog/2022/08/brief-introduction-to-arc42/)
- [Diátaxis](https://diataxis.fr/)
- [Emmanuel Bernard: Exploring Diátaxis](https://emmanuelbernard.com/blog/2024/12/19/diataxis/)
- [Sequin: We fixed our documentation with Diátaxis](https://blog.sequinstream.com/we-fixed-our-documentation-with-the-diataxis-framework/)
- [Awesome Copilot documentation-writer skill](https://github.com/github/awesome-copilot/blob/main/skills/documentation-writer/SKILL.md)
- [Awesome Copilot technical-writer agent](https://github.com/github/awesome-copilot/blob/main/agents/se-technical-writer.agent.md)
- [Awesome Copilot project-documenter agent](https://github.com/github/awesome-copilot/blob/main/agents/project-documenter.agent.md)

## Design

1. Add one path-specific Markdown instruction and one reusable documentation-writer skill.
2. Add a reference style contract and a task-oriented authoring guide.
3. Refactor the documentation-system explanation, goal workflow, architecture index, roadmap, graph
   boundary, and validation guidance to use the new tone and evidence vocabulary.
4. Synchronize `AGENTS.md`, Copilot, Claude, Python, GitHub Actions, README, and site navigation.
5. Track the next graph step as `KG-001` without implementing it.

## Files

- Authoring contract: `.github/instructions/documentation.instructions.md`,
  `.github/skills/documentation-writer/SKILL.md`, `docs/reference/documentation-style.md`,
  `docs/how-to/write-documentation.md`.
- Site and guidance: `zensical.toml`, `docs/index.md`, `docs/explanation/`, `docs/how-to/`,
  `docs/reference/knowledge-graph.md`, `docs/roadmap/index.md`, `README.md`.
- Adapters: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`,
  `.github/instructions/python.instructions.md`, `.github/instructions/github-actions.instructions.md`.
- Spec record: `specs/013-documentation-style-governance/`.

## Validation tiers

- Focused: `uv run just docs-build` and internal-link/diagram review.
- Root fast: `uv run just check`, `uv run just test-unit`, and `uv run just test`.
- Handoff: `uv run just coverage-ci` and `uv run just audit`; package checks remain unchanged
  because this feature does not modify distribution behavior.
- Nested: run the nested checks when its documentation or command boundary changes.
- Deferred: `KG-001` requires a separate graph contract and deterministic query evidence.

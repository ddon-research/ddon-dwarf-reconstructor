# Documentation style

This reference defines how contributors write, organize, review, and retire documentation for the
DDON DWARF Reconstructor. It is for maintainers, implementation contributors, and automation that
creates or changes Markdown. The contract combines Diátaxis for reader intent with arc42 for
architecture communication.

## The governing decision

Use Diátaxis to decide what a page is for. Use arc42 to decide how architecture explanations are
organized. Use source evidence and Spec Kit records to decide what the page may claim. These
frameworks complement each other; neither replaces code, tests, manifests, or feature specs.

The site is a docs-as-code publication surface. Markdown, Mermaid source, navigation, and this
style contract are reviewed in Git. Zensical validates the site and publishes a static build.

## Page intent

| Page type | Reader state | Page promise | Keep out | Typical location |
| --- | --- | --- | --- | --- |
| Tutorial | Learning by doing | A newcomer reaches one verified outcome | Architecture lectures, exhaustive options, unrelated troubleshooting | `docs/tutorials/` |
| How-to guide | Solving a known problem | A capable contributor completes one task | General lessons, full API inventory, unrelated history | `docs/how-to/` |
| Reference | Looking up a fact or contract | A precise, searchable description of machinery | Opinions, step-by-step teaching, unexplained rationale | `docs/reference/` |
| Explanation | Building understanding | The reader understands context, reasons, and trade-offs | Command catalogs and procedural checklists | `docs/explanation/` |
| Knowledge-base note | Evaluating evidence | A research finding can be revalidated | Claims presented as current runtime behavior | `docs/knowledge-base/` |

Specs are the intent and roadmap record, not a fifth Diátaxis page type. A spec names scope,
requirements, exact paths, tasks, and validation evidence. The site should link to it rather than
copy its requirements.

When a page seems to need two types, split it. A how-to can link to an explanation for “why” and a
reference page for exact options. A tutorial can link forward without becoming a textbook.

Use the page set as a product signal. A tutorial should deliver one small, observable win; a
how-to should expose a real user problem and its trade-offs; missing reference pages can be tracked
as explicit links or roadmap tasks. This keeps documentation useful while it also reveals awkward
workflows that may need a product or tooling change.

## Tone and language

Write as a careful engineering partner: calm, direct, precise, and explicit about uncertainty.

- Start with the reader's task, question, or decision. State the result before background when the
  page is operational.
- Prefer active voice and present tense: “The publisher writes a manifest,” not “A manifest is
  written.” Use `you` for instructions and neutral project language for contracts.
- Use one main idea per paragraph. Keep sentences short when the concept is difficult; use a table
  when repeated mappings are easier to scan than prose.
- Use exact names from the codebase: commands, options, classes, paths, artifact names, and status
  values. Define uncommon terms and abbreviations at first use.
- Prefer concrete evidence over adjectives. Say which test, manifest, source path, or command
  supports a claim. Avoid marketing language, filler, and unqualified “always,” “never,” “simple,”
  or “obvious.” Use explicit safety prohibitions where data or credentials are at risk.
- Do not duplicate a maintained contract merely to make a page feel complete. Link to it, explain
  its relevance, and remove the page when it no longer adds information.

## Evidence vocabulary

Use these labels when a reader could mistake intent, observation, or inference for implemented
behavior:

| Label | Meaning | Minimum support |
| --- | --- | --- |
| `Implemented` | The behavior exists in the checked-in source | Source path |
| `Verified` | The behavior passed a named deterministic check | Test or command and result |
| `Observed` | An external tool or real asset produced the result | Source/tool/profile/output manifest |
| `Approximate` | A bounded inference or additive cross-check | Evidence plus the authority limit |
| `Deferred` | Deliberately outside the current slice | Roadmap/spec task and next step |
| `Blocked` | Progress needs an unavailable external prerequisite | Blocker, attempted check, and unblock action |
| `Obsolete` | No longer maintained or true | Remove from active navigation; Git retains history |

For this project, owning DWARF producer facts remain authoritative. External tool observations are
additive. Missing, partial, conflicting, unavailable, and real-asset evidence stays visible. A
static page must not imply that a live LadybugDB database, graph browser, compiler validation, or
proprietary-tool run exists when the repository has only a JSONL bundle or a deferred task.

## Architecture writing with arc42

Architecture pages are explanation pages. Use the arc42 compartments as a stable vocabulary and
tailor the depth to stakeholder need; an empty compartment is acceptable.

| arc42 section | Question | Local mapping |
| --- | --- | --- |
| 1. Introduction and goals | What matters, to whom, and why? | [System context](../explanation/architecture/context.md) |
| 2. Constraints | What limits the solution? | [Decisions and trade-offs](../explanation/architecture/decisions.md) |
| 3. Context and scope | What is inside and outside the system? | [System context](../explanation/architecture/context.md) |
| 4. Solution strategy | Which ideas shape the solution? | [Containers and building blocks](../explanation/architecture/containers.md) |
| 5. Building block view | What are the stable responsibilities and boundaries? | [Components and boundaries](../explanation/architecture/components.md) |
| 6. Runtime view | How do important scenarios execute? | [Runtime flows](../explanation/architecture/runtime.md) |
| 7. Deployment view | Where does it run and what persists? | [Deployment and operations](../explanation/architecture/deployment.md) |
| 8. Cross-cutting concepts | Which policies recur across components? | [Crosscutting concepts](../explanation/architecture/crosscutting-concepts.md) |
| 9. Architecture decisions | Which important choices and alternatives matter? | [Decisions and trade-offs](../explanation/architecture/decisions.md) |
| 10. Quality requirements | How do we recognize acceptable behavior? | [Testing reference](testing.md) and [deployment](../explanation/architecture/deployment.md) |
| 11. Risks and technical debt | What remains uncertain or expensive? | [Roadmap](../roadmap/index.md) and feature specs |
| 12. Glossary | Which terms need stable meaning? | [CLI reference](cli.md), [knowledge base](../knowledge-base/README.md), and page-local definitions |

Write architecture top-down. Begin with goals and context, then expose only the detail needed to
understand a decision or scenario. Name the responsibility of each important black box, map it to
source structure, and explain why a white-box decomposition exists. Record constraints, trade-offs,
risks, and deferred work instead of presenting an idealized design.

Architecture decisions should include status, date, context, decision, consequences, alternatives,
and evidence. A decision without its reason is a code-shaped fact, not useful architecture
communication.

## Diagrams as code

Keep Mermaid source in the Markdown page. Select the smallest standard diagram that answers the
reader's question:

- `C4Context` for people, systems, and external dependencies;
- `C4Container` for independently replaceable applications and data stores inside a system;
- `C4Component` for a container's major responsibilities and adapters;
- `flowchart` for system context, boundaries, and pipelines;
- `sequenceDiagram` for a runtime scenario;
- `stateDiagram-v2` for lifecycle or workflow transitions;
- `classDiagram` for UML structure, ownership, and contracts;
- `erDiagram` for stable record and relationship shapes.

Every diagram must have one purpose, meaningful labels, and nearby prose or a table that explains
important nodes and relationships. Keep one abstraction level per diagram: do not mix system,
container, component, and code symbols. Use standard UML semantics for class diagrams. Mermaid C4
is experimental, so use it for stable semantic maps and retain a native flowchart or UML view when
the C4 renderer cannot express the reader's question. Quote labels containing punctuation, keep
IDs stable, label every important relationship, and avoid generic node names or unexplained
acronyms. Do not use a diagram to show every source symbol, and do not commit an exported image
when the Mermaid source is the maintainable artifact.

## Authoring and review loop

1. **Classify.** Choose the page type and record audience, outcome, scope, and prerequisites.
2. **Inventory.** Read the current page, navigation, source, tests, active spec, and relevant
   research. Preserve unrelated edits and local durable evidence.
3. **Outline.** Put the reader's outcome first and make excluded content explicit when scope is
   easy to misunderstand.
4. **Write.** Use the project voice, progressive disclosure, exact commands, and source links.
5. **Model.** Add the smallest set of Mermaid diagrams that answer distinct questions; use C4 for
   architecture abstraction levels and UML/sequence/state diagrams for code or runtime detail.
   Explain each diagram in nearby text.
6. **Label.** Attach implementation status, evidence, authority, uncertainty, and the next step.
7. **Synchronize.** Update navigation, README, roadmap/spec, and applicable instruction adapters.
8. **Validate.** Run `uv run just docs-check`, then `uv run just check` and relevant tests. For
   nested tooling use `uv run --directory tools/dwarf_spec_pipeline ...`.
9. **Retire.** Remove obsolete duplicate pages and stale links. Git history is the archive.

The review is complete only when the page is findable, internally linked, source-backed, readable
for its intended audience, and maintainable by the next contributor.

## External foundations

This local contract is informed by [arc42's documentation template](https://arc42.org/documentation/),
the [arc42 practical tips](https://docs.arc42.org/home/), its [keyword-indexed guidance](https://docs.arc42.org/keywords/),
[arc42's FAQ](https://faq.arc42.org/home/), and [INNOQ's brief arc42 introduction](https://www.innoq.com/en/blog/2022/08/brief-introduction-to-arc42/).
It uses the [Diátaxis framework](https://diataxis.fr/) together with [Emmanuel Bernard's practical
view](https://emmanuelbernard.com/blog/2024/12/19/diataxis/) and [Sequin's account of using
Diátaxis](https://blog.sequinstream.com/we-fixed-our-documentation-with-the-diataxis-framework/).
The reusable instruction shape is adapted from the [GitHub Awesome Copilot documentation-writer
skill](https://github.com/github/awesome-copilot/blob/main/skills/documentation-writer/SKILL.md),
the [technical-writer agent](https://github.com/github/awesome-copilot/blob/main/agents/se-technical-writer.agent.md),
and the [project-documenter agent](https://github.com/github/awesome-copilot/blob/main/agents/project-documenter.agent.md).
The emphasis on correctness, currency, relevance, maintainability, findability, version control,
and continuous updates follows [INNOQ's principles of technical documentation](https://www.innoq.com/en/blog/2022/01/principles-of-technical-documentation/).
The architecture visualization contract also follows the [C4 model](https://c4model.com/),
[Mermaid C4 syntax](https://mermaid.ai/open-source/syntax/c4.html), the [Mermaid syntax reference](https://mermaid.ai/open-source/intro/syntax-reference.html),
and the [GitLab Mermaid guidance](https://handbook.gitlab.com/handbook/tools-and-tips/mermaid/).

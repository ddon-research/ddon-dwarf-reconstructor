# Documentation system

The repository uses three complementary structures:

- **Diátaxis** assigns each page one reader need: learn, solve, look up, or understand.
- **arc42** gives architecture explanations a stable vocabulary from goals and context through
  building blocks, runtime, deployment, decisions, quality, risks, and glossary.
- **Spec Kit** records intent, scope, exact implementation paths, validation tiers, and unfinished
  work. The [roadmap](../roadmap/index.md) indexes those records without copying their requirements.

The [documentation style reference](../reference/documentation-style.md) is the authoring contract.
The [documentation how-to](../how-to/write-documentation.md) is the task procedure. Together they
define tone, evidence language, diagram policy, and review expectations for Codex, Copilot, Claude,
and human contributors.

Zensical turns the Markdown tree into a searchable static site. Mermaid source remains in the page;
the generated site is a build product. C4 context/container/component diagrams map architecture at
progressive abstraction levels; flowcharts, sequence/state diagrams, ER diagrams, and UML class
diagrams answer narrower boundary, runtime, data, and code questions. Each diagram is reviewed
beside the explanatory text.

## Source-of-truth order

For a claim about current behavior, use this order:

1. Executable source, typed contracts, and tests define what the repository does.
2. Deterministic manifests and generated specification artifacts preserve producer or build facts.
3. Spec Kit artifacts define intended work and acceptance evidence; they do not make an unchecked
   task implemented.
4. The site explains and indexes the current boundary; it must not contradict source or specs.
5. Knowledge-base notes preserve research and external evidence with an explicit authority and
   status label.

When a page becomes stale, update the source-backed page or remove the obsolete narrative. Do not
keep parallel architecture, testing, goal, or graph pages with competing commands or claims.

## Architecture and reader boundaries

Architecture pages live under `docs/explanation/architecture/` and use the relevant arc42
compartments. They are explanation pages, not command references. How-to guides link to them when a
reader needs rationale; [crosscutting concepts](architecture/crosscutting-concepts.md) is the
section-8 home for policies that span building blocks; reference pages state exact contracts without
importing the essay.

The knowledge base is an evidence ledger. It may contain exploratory or historical material, but it
must link forward to a current reference or explanation page before a finding becomes a project
contract.

## Current capability boundary

The reconstructor exports a deterministic JSONL knowledge bundle. It does not currently publish a
Neo4j database, graph API, interactive graph view, or documentation-to-code dependency index. The
versioned loader and deterministic query fixtures are tracked as `KG-001` in the
[documentation style feature](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/013-documentation-style-governance).
The static site documents this boundary; it does not imply that future infrastructure exists.

## Maintenance rule

For every cross-module change:

1. classify the affected page by reader need;
2. update the smallest affected Diátaxis page and relevant arc42 compartment;
3. update the active spec, roadmap, and instruction adapter when the contract changes;
4. label evidence, uncertainty, and deferred work;
5. run `uv run just docs-build` and the applicable repository gates.

The strict site build is part of `uv run just check`. Git history is the archive for retired prose;
active navigation should contain one maintained explanation of each contract.

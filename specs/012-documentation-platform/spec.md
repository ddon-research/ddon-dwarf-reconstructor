# Feature Specification: Source-backed documentation platform

**Feature branch:** `012-documentation-platform`
**Status:** Implemented, acceptance-verified, and publicly deployed on GitHub Pages
**Owner:** DDON DWARF Reconstructor maintainers

## Problem

The repository's documentation is a collection of large, overlapping Markdown narratives. The
architecture, generation flow, testing, goal workflow, and tag-analysis pages duplicate source
behavior and contain command/path drift. There is no checked-in static-site configuration, no
published navigation model, no architecture diagram source of truth, and no visible index of the
Spec Kit roadmap.

## Outcome

The repository shall publish a source-backed, searchable static wiki through Zensical and GitHub
Pages. Its navigation shall follow Diátaxis page intent, its architecture explanation shall follow
arc42, diagrams shall be Mermaid/UML source in Markdown, and Spec Kit features shall remain the
roadmap and decision record. The site shall document the current JSONL knowledge-graph projection
without claiming that a live graph database or browser exists.

## Requirements

- **DOC-001**: `zensical.toml` MUST define the site identity, explicit navigation, strict Mermaid
  fence support, and a GitHub Pages-compatible `site` build.
- **DOC-002**: `docs/` MUST provide tutorial, how-to, explanation, reference, roadmap, and
  knowledge-base paths with no competing flat architecture/testing/goal source pages.
- **DOC-003**: Architecture pages MUST cover arc42 context, constraints, containers, components,
  runtime, deployment, decisions, quality risks, and evidence boundaries.
- **DOC-004**: At least one flowchart, sequence/state diagram, and UML class diagram MUST be kept
  as Mermaid source and rendered by the site build.
- **DOC-005**: The roadmap MUST index features 001-012 with status derived from their specs/tasks;
  it MUST link to the authoritative Spec Kit records rather than copying requirements.
- **DOC-006**: The CLI, artifact, testing, source-identity, knowledge-export, and low-level
  type-resolution pages MUST reflect the current implementation and preserve uncertainty.
- **DOC-007**: The root `justfile` MUST expose `docs-serve` and strict `docs-build`; `docs-build`
  MUST be part of `just check` and the root development dependency lock.
- **DOC-008**: A Pages workflow MUST build from the locked uv environment and pin all external
  actions to full SHAs, while keeping deployment permissions limited to the Pages job.
- **DOC-009**: README, AGENTS, Copilot, Claude, Python, GitHub Actions, and test guidance MUST
  point to the new documentation source and canonical nested-project commands.
- **DOC-010**: Obsolete duplicate documentation MUST be removed after its current source-backed
  content is represented in the new site; unrelated worktree changes and generated evidence MUST
  remain untouched.

## Acceptance scenarios

1. A fresh checkout can run `uv sync --python 3.14.6` and `uv run just docs-build` to produce
   `site/` without strict-build errors.
2. A reader can navigate from the site home to a tutorial, a task guide, architecture diagrams,
   a CLI contract, the knowledge-graph boundary, and the Spec Kit roadmap.
3. `uv run just check` includes the documentation build and remains aligned with hosted CI.
4. A documentation review can distinguish implemented behavior, deterministic integration evidence,
   real-asset evidence, deferred prerequisites, and future graph infrastructure.
5. The final diff contains no changes to pre-existing unrelated edits or local source-bound cache
   artifacts.

## Non-goals

- Building a Neo4j server, graph API, or interactive graph browser in this feature.
- Moving or publishing proprietary ELF/dump inputs, generated headers, credentials, or runtime
  caches.
- Replacing the existing graph export contract or changing reconstruction semantics.
- Treating GitHub repository settings or Pages activation as enabled solely by a checkout change.

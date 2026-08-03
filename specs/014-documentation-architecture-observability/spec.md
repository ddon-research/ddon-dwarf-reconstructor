# Feature specification: source-backed architecture and developer how-tos

**Status:** Implemented, merged, and publicly verified on GitHub Pages

## Intent

Refine the static documentation site after the first platform migration. Move Langfuse and
SonarQube material into developer-focused Diátaxis how-to pages, give arc42 section 8 a central
crosscutting-concepts page, and add source-backed C4/UML/Mermaid views without claiming deferred
runtime telemetry or graph ingestion exists.
The deferred LadybugDB-first graph evaluation is tracked in the
[KG-001 feature record](../015-ladybugdb-knowledge-graph/spec.md).

## Requirements

- **DOC-014-1:** Langfuse instructions MUST be a how-to that distinguishes loopback deployment,
  Copilot configuration, Codex configuration, privacy controls, verification, and destructive
  lifecycle operations.
- **DOC-014-2:** SonarQube instructions MUST be a how-to that reflects the current
  `prepare_msvc_analysis` adapter, strict versus analysis-only exit behavior, generated input
  layout, and the distinction between producer facts and additive diagnostics.
- **DOC-014-3:** The arc42 architecture index MUST map section 8 to one crosscutting concepts page
  that links each concept to source paths, tests, how-tos, authority, and uncertainty.
- **DOC-014-4:** Architecture pages MUST contain useful C4 context/container/component views and
  retain native Mermaid UML/sequence views where they answer a more specific code or runtime
  question.
- **DOC-014-5:** Mermaid source MUST remain in Markdown, use one purpose per diagram, label
  important relationships, avoid mixed abstraction levels, and be checked by the strict site build
  and a Mermaid parser.
- **DOC-014-6:** Retired flat Langfuse/SonarQube pages and their active links MUST be removed after
  migration; no duplicate operational contract may remain.
- **DOC-014-7:** Documentation navigation, README, roadmap/spec, contributor instructions, and
  Copilot/Codex adapters MUST remain synchronized.
- **DOC-014-8:** Publication MUST be committed, pushed, attached to the existing documentation/CI
  pull request, and verified at the configured GitHub Pages URL; a Pages settings limitation must
  be reported as a concrete remote blocker if it cannot be changed with the available authority.
- **DOC-014-9:** The documentation quality loop MUST pin and run the official Mermaid CLI for every
  Mermaid fence and `markdownlint-cli2` for authored site Markdown before the strict Zensical build.

## Evidence boundary

Current behavior comes from the observability modules and tests, Sonar adapter and tests, Langfuse
Compose/just recipes, the existing Zensical workflow, and the locked Node documentation-tool
package. Real Copilot/Codex traces, MSVC/Sonar execution, and public Pages availability are
environmental or remote evidence and must be reported separately from the deterministic local site
build.

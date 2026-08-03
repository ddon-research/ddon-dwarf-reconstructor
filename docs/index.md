# DDON DWARF Reconstructor

The DDON DWARF Reconstructor turns ELF/DWARF evidence into deterministic C++ headers and
source-bound knowledge bundles. This site is the project wiki: it explains how to use the tool,
why the architecture is shaped as it is, and where the implementation roadmap is heading.

The documentation is deliberately source-backed. A claim about behavior must be traceable to
the Python implementation, a test, a generated artifact, or an explicitly identified external
tool result. Spec Kit features remain the roadmap and decision record; this site is the usable
explanation and reference layer around them.

## Start here

- New to the repository: [First generation](tutorials/first-generation.md).
- Running a normal change: [Validate changes](how-to/validate-changes.md).
- Understanding the system: [Architecture overview](explanation/architecture/index.md).
- Looking for a command or option: [CLI reference](reference/cli.md).
- Checking planned work: [Roadmap](roadmap/index.md).

## Documentation map

| Need | Where to look |
| --- | --- |
| Learn the workflow end to end | [Tutorials](tutorials/first-generation.md) |
| Complete one operational task | [How-to guides](how-to/generate-headers.md) |
| Understand design and trade-offs | [Architecture](explanation/architecture/index.md) |
| Configure developer tooling | [Langfuse tracing](how-to/observability/langfuse.md) and [SonarQube analysis](how-to/quality/sonarqube.md) |
| Look up a stable contract | [Reference](reference/cli.md) |
| Create or review documentation | [Documentation style](reference/documentation-style.md) |
| Explore source investigations and external evidence | [Knowledge base](knowledge-base/README.md) |
| See intended and deferred work | [Roadmap](roadmap/index.md) |

## Evidence boundaries

The repository contains three related but distinct evidence surfaces:

1. The reconstructor produces deterministic headers, manifests, caches, and knowledge bundles.
2. The knowledge base records source analysis, specifications, and bounded external-tool evidence.
3. This site publishes the explanation and navigation layer; it does not replace generated output
   or claim that a real PS4/compiler/performance check ran when it did not.

Real ELF inputs, expanded dumps, generated headers, caches, logs, and credentials remain local
artifacts. The public site is safe to build from the checked-in Markdown and generated
specification artifacts.

## Project links

- [Source repository](https://github.com/ddon-research/ddon-dwarf-reconstructor)
- [Issue tracker](https://github.com/ddon-research/ddon-dwarf-reconstructor/issues)
- [Goal-oriented workflow](how-to/goal-oriented-workflow.md)
- [Write or update documentation](how-to/write-documentation.md)

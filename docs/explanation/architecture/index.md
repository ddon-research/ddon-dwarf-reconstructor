# Architecture overview

This is the arc42 entry point for the reconstructor. It describes the system that exists in the
source tree today. Deferred real-asset, compiler, and live-graph work stays labelled as deferred;
this index does not turn roadmap intent into implementation evidence.

## Arc42 map

| arc42 concern | Project page |
| --- | --- |
| 1. Introduction and goals | [System context](context.md) |
| 2. Constraints | [Decisions and trade-offs](decisions.md) |
| 3. Context and scope | [System context](context.md) |
| 4. Solution strategy | [Containers and building blocks](containers.md) |
| 5. Building block view | [Components and boundaries](components.md) |
| 6. Runtime view | [Runtime flows](runtime.md) |
| 7. Deployment view | [Deployment and operations](deployment.md) |
| 8. Cross-cutting concepts | [Crosscutting concepts](crosscutting-concepts.md) |
| 9. Architecture decisions | [Decisions and trade-offs](decisions.md) |
| 10. Quality requirements | [Testing reference](../../reference/testing.md) and [deployment](deployment.md) |
| 11. Risks and technical debt | [Roadmap](../../roadmap/index.md) and feature specs |
| 12. Glossary | [CLI reference](../../reference/cli.md) and [knowledge base](../../knowledge-base/README.md) |

Arc42 compartments are optional. This project groups related concerns when that makes the site
easier to navigate, but each page keeps its question and evidence boundary explicit.

## Architectural boundary

The project has a root reconstructor and a separate `tools/dwarf_spec_pipeline` uv project. The
root follows a hexagonal direction: domain models and ports are inner contracts, application
services coordinate use cases, and infrastructure owns pyelftools, SQLite, zstd, filesystems,
external tools, and logging adapters. Composition roots are the only place that constructs outer
adapters.

The architecture stays technology-agnostic at the domain boundary while remaining explicit about
the evidence-preservation responsibilities that make a DWARF reconstructor safe. See the
[documentation style reference](../../reference/documentation-style.md) for the full arc42 writing
and diagram contract.

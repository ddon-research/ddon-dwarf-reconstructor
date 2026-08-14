# Containers and building blocks

The repository has two independently locked Python projects and several non-Python boundaries.
The C4 container view shows the deployable or independently replaceable responsibilities; it is
not intended to mirror every Python package.

```mermaid
C4Container
title "DDON DWARF Reconstructor — containers"
Person(developer, "Developer or automation", "Runs repository commands.")
System_Boundary(reconstructor, "DDON DWARF Reconstructor") {
    Container(cli, "Typer CLI", "Python / Typer", "Canonical command surface for generation, knowledge export, and artifact inspection.")
    Container(workflows, "Application workflows", "Typed Python", "Coordinates use cases through ports without constructing adapters.")
    ContainerDb(evidenceStore, "Source-bound evidence stores", "SQLite, JSON, manifests", "Indexes, caches, and fingerprints keyed by source and producer identity.")
    Container(outputs, "Deterministic output publishers", "Filesystem adapters", "Atomically publishes generated headers, manifests, and JSONL knowledge bundles.")
    Container(specPipeline, "DWARF specification pipeline", "Independent uv project", "Builds and audits canonical specification JSON and Markdown.")
}
System_Ext(source, "ELF/DWARF and compressed dumps", "Immutable source evidence")
System_Ext(externalTools, "External inspection and compiler tools", "Optional additive evidence and local validation")
System_Ext(consumers, "Header, graph, and analysis consumers", "Reads published artifacts")
System_Ext(site, "Zensical documentation site", "Builds the checked-in docs tree")
Rel(developer, cli, "Runs commands")
Rel(cli, workflows, "Dispatches typed requests")
Rel(workflows, evidenceStore, "Reads and writes validated durable evidence")
Rel(workflows, outputs, "Publishes deterministic bundles")
Rel(source, workflows, "Provides source evidence")
Rel(externalTools, workflows, "Adds named observations or validation results")
Rel(outputs, consumers, "Publishes headers, manifests, and JSONL")
Rel(developer, site, "Reads docs")
Rel(specPipeline, site, "Supplies generated specification pages")
```

The repository also keeps a UML-style building-block view because the C4 diagram intentionally
omits implementation-level method contracts:

```mermaid
classDiagram
    class CLI {
        +generate(request)
        +export_knowledge(request)
        +artifacts(command)
    }
    class DwarfGenerator {
        +generate_bundle(request) HeaderBundle
        +export_knowledge_graph(request) KnowledgeBundle
    }
    class GenerationFacade {
        +generate_bundle(request) HeaderBundle
        +export_knowledge_graph(request) KnowledgeBundle
    }
    class GenerationRuntime {
        +begin_root(symbol)
        +end_root()
        +close()
    }
    class HeaderRenderer {
        +generate_single(class_info)
        +generate_hierarchy(hierarchy)
    }
    class DorisDwarfStore {
        +find_primary_definition(name) QueryResult
        +begin_root(symbol)
        +end_root()
    }
    class MaterializedStorePort {
        <<protocol>>
        +find_definitions(name) QueryResult
        +children_for_die(offset)
    }
    class DorisLoader {
        +execute(plan) LoadReport
    }
    class ElfDwarfSession {
        +open(source)
        +close()
    }
    class SourceIdentityCatalog {
        +identify(source) SourceIdentity
        +verify(source) SourceIdentity
    }
    class AtomicHeaderPublisher {
        +publish(bundle) Manifest
        +rollback()
    }
    class DwarfSpecPipeline {
        +build()
        +validate()
        +audit()
    }

    CLI --> DwarfGenerator : composition root
    DwarfGenerator --> GenerationFacade
    GenerationFacade --> GenerationRuntime
    GenerationRuntime --> HeaderRenderer
    GenerationRuntime --> DorisDwarfStore
    GenerationRuntime --> MaterializedStorePort : validation only
    GenerationFacade --> ElfDwarfSession
    ElfDwarfSession --> SourceIdentityCatalog
    GenerationFacade --> AtomicHeaderPublisher
    DorisLoader --> MaterializedStorePort : loads canonical rows
    DwarfSpecPipeline ..> GenerationFacade : separate project boundary
```

The `core` package contains technology-neutral contracts and observability/path boundaries.
`domain` owns evidence models, parsing policy, type/declarator logic, and generation policy.
`application` coordinates use cases through ports. `infrastructure` implements ELF/DWARF,
SQLite, zstd, filesystem, external-tool, configuration, and logging adapters.

The graph exporter is an application projection over the same producer facts. It must not become
a second definition-selection or evidence-authority implementation.

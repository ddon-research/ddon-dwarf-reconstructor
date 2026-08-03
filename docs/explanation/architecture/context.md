# System context

The following C4 system-context view deliberately stays at the repository boundary. It answers
who uses the system and which external inputs and consumers matter; it is not a module inventory.

```mermaid
C4Context
title "DDON DWARF Reconstructor — system context"
Person(developer, "Developer or automation", "Runs deterministic reconstruction, export, and artifact commands.")
System(reconstructor, "DDON DWARF Reconstructor", "Reads source evidence and publishes deterministic headers, manifests, and knowledge bundles.")
System_Ext(elfInput, "ELF/DWARF or compressed dump", "Immutable PS4/PS3 producer evidence, optionally indexed for bounded lookup.")
System_Ext(toolEvidence, "Optional inspection tools", "Orbis, LLVM, GNU, elfutils, libdwarf, pyelftools, LIEF, or OpenOrbis observations.")
System_Ext(headerConsumer, "C/C++ or analysis consumer", "Consumes generated headers or compilation databases.")
System_Ext(graphConsumer, "Future graph loader", "Neo4j or equivalent; the current contract is a JSONL bundle, not a live graph.")
System_Ext(site, "Published documentation site", "Zensical renders checked-in Markdown and generated specification artifacts.")
Rel(developer, reconstructor, "Runs typed CLI commands")
Rel(elfInput, reconstructor, "Provides source evidence")
Rel(toolEvidence, reconstructor, "Adds bounded, provenance-labelled observations")
Rel(reconstructor, headerConsumer, "Publishes headers and manifests")
Rel(reconstructor, graphConsumer, "Exports JSONL knowledge bundle")
Rel(developer, site, "Reads architecture, how-to, reference, and research pages")
```

Mermaid's C4 syntax is experimental. This view therefore communicates stable system semantics,
while the repository's native flowcharts, sequence diagrams, and UML class diagrams remain the
fallback when a reader needs a view that C4 does not express well.

The reconstructor consumes immutable ELF/DWARF or bounded compressed-dump inputs and produces
deterministic headers, manifests, and graph-shaped knowledge bundles. External tools are optional
evidence producers, not hidden dependencies of the offline path.

```mermaid
flowchart LR
    developer["Developer or automation"] --> cli["Typer CLI\ngenerate / export-knowledge / artifacts"]
    cli --> app["Application use cases"]
    app --> domain["Domain models and services"]
    domain --> ports["Ports\nlookup, cache, identity, tools"]
    ports --> infra["Infrastructure adapters"]
    infra --> elf["ELF/DWARF input"]
    infra --> dump["Compressed dump\nstreaming SQLite index"]
    infra --> cache["Source-bound caches\nand manifests"]
    infra --> tools["Optional external tools\nadditive evidence"]
    app --> headers["Atomic generated headers"]
    app --> knowledge["Knowledge bundle\nJSONL + manifest"]
    headers --> consumer["C/C++ or analysis consumer"]
    knowledge --> graph_loader["Future graph loader\nNeo4j or equivalent"]
```

The site is a separate publication consumer of checked-in Markdown and generated DWARF
specification artifacts. It does not sit in the reconstruction runtime path.

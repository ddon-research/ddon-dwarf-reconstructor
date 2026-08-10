# Runtime flows

## Header generation

```mermaid
sequenceDiagram
    actor User
    participant CLI
    participant Workflow as Application workflow
    participant Store as Source-bound DWARF store
    participant Index as Doris serving query port
    participant Lookup as Promoted b8 source/name lookup
    participant Parser as Class/type services
    participant Publisher as AtomicHeaderPublisher

    User->>CLI: generate ELF + symbol
    CLI->>Workflow: GenerationRequest
    Workflow->>Store: validate manifest and source identity
    Workflow->>Index: lookup definition
    Index->>Lookup: source/name key lookup
    Lookup-->>Index: bounded ordered candidates
    Index-->>Workflow: SearchResult + provenance
    Workflow->>Parser: resolve class, types, methods, hierarchy
    Parser-->>Workflow: typed evidence model
    Workflow->>Publisher: stage headers + manifest
    Publisher-->>Workflow: committed HeaderBundle
    Workflow-->>CLI: JSON/result path
```

The compiler audit is a separate, change-triggered evidence path rather than a normal generation
dependency:

```mermaid
flowchart LR
    Roots["Season 2 root list"] --> Generator["Source-bound generator"]
    Generator --> Bundles["Atomic header bundles and manifests"]
    Bundles --> Validator["MSVC: one translation unit per header"]
    Validator --> Report["Structured pass, warning, or failure report"]
    Report --> Decision["Syntax and closure acceptance"]
    Bundles --> Parity["Ordered hashes and provenance"]
    Parity --> Decision
    External["IDA/Sonar or approved baseline"] --> Decision
```

The final Season 2 report passed all 2,760 headers. Warning-only compiler diagnostics remain
evidence; they do not become generated code or runtime dependencies.

## Knowledge export

The exporter shares the session, lookup, definition selection, type resolution, and evidence
authority with generation. It then serializes nodes, relationships, instructions, reconstructed
C++, and a manifest. The projection is deterministic and can be loaded by a future graph system.

## Durable reuse

Source identity is checked before a cache or dump index is reused. A warm key may avoid another
full hash when filesystem metadata proves the same object; explicit `verify` always rehashes the
complete source. The normal generation path consumes the source-bound analytical store and never
implicitly performs the expensive CU traversal. A failed atomic materialization leaves the previous
valid store available; the compressed-text SQLite index remains a validation-only cross-check.

# Knowledge graph contract

The current graph projection is a deterministic interchange bundle. It is deliberately useful
without a database server and explicit about what has not yet been built.

```mermaid
erDiagram
    SOURCE ||--o{ COMPILATION_UNIT : contains
    COMPILATION_UNIT ||--o{ DIE : owns
    DIE ||--o{ TYPE : defines_or_references
    DIE ||--o{ MEMBER : declares
    DIE ||--o{ METHOD : declares
    DIE ||--o{ EVIDENCE : produces
    EVIDENCE ||--o{ TOOL_OBSERVATION : cross_checks
    DIE ||--o{ RELATIONSHIP : connects
```

## Published records

`nodes.jsonl` contains typed producer and evidence nodes. `relationships.jsonl` contains stable
edges. `instructions.jsonl` records reconstruction or consumer guidance. `reconstructed_cpp`
provides a human-readable projection, and `manifest.json` binds the bundle to its source,
configuration, schema, and checksums.

## Authority and uncertainty

The owning DIE is authoritative for producer facts. Tool observations are additive and retain
their tool/profile/source provenance. Missing data is represented as `not_observed`; partial
search results are not complete evidence. Conflicting or unavailable observations remain visible.

## Next graph step

The repository does not currently publish a LadybugDB database, graph API, or interactive graph
view. The next implementation is a LadybugDB-first evaluation and versioned loader over the
existing JSONL contract. It must preserve producer authority, validate source checksums, and add
deterministic query fixtures before a live deployment is introduced.

The unchecked `KG-001` task is defined in the
[dedicated LadybugDB knowledge-graph feature](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/015-ladybugdb-knowledge-graph).
LadybugDB is a proposed derived read model, not current runtime behavior; this static site does
not imply that the loader or a live deployment exists.

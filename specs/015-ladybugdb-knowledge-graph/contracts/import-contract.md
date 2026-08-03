# LadybugDB import contract

This contract defines the derived LadybugDB projection for `KG-001`. It does not replace the
canonical JSONL bundle described in `docs/reference/knowledge-graph.md`.

## Input boundary

The loader accepts a directory containing:

- `manifest.json`;
- `nodes.jsonl`;
- `relationships.jsonl`;
- optional `instructions.jsonl`;
- optional manifest-declared projections such as `reconstructed.hpp`.

The loader MUST validate that every required file exists, every declared SHA-256 matches, the
bundle schema is supported, and every relationship endpoint resolves to an imported node before it
opens a write transaction. JSONL input is streamed; the implementation MUST NOT load the complete
bundle into an unbounded in-memory collection.

## LadybugDB projection

The default schema uses one stable table per record family so the heterogeneous producer graph can
be imported without inventing a separate source type for every `kind` or relationship `type`.
LadybugDB's native `JSON` type is required for the `properties` and `payload` columns; silently
flattening or stringifying those values is not an accepted fallback.

| Table | Required fields | Derivation and authority |
| --- | --- | --- |
| `KnowledgeNode` | `id STRING PRIMARY KEY`, `kind STRING`, `properties JSON`, `search_text STRING` | `id`, `kind`, and `properties` come from `nodes.jsonl`; `search_text` is derived only from the fixed textual fields `name`, `qualified_name`, `signature`, `description`, and `text`. |
| `KnowledgeEdge` | `FROM KnowledgeNode TO KnowledgeNode`, `edge_id STRING`, `type STRING`, `properties JSON` | `source_id`, `type`, `target_id`, and `properties` come from `relationships.jsonl`; `edge_id` is the SHA-256 of the canonical relationship record and preserves distinct records with different properties. |
| `KnowledgeInstruction` | `id STRING PRIMARY KEY`, `function_id STRING`, `payload JSON` | `function_id` and the complete instruction record come from `instructions.jsonl`; `id` is the SHA-256 of the canonical instruction record. |

The loader MUST NOT use database-generated IDs for source records. A database-generated internal
ID MAY be used by LadybugDB for query execution, but it is not a provenance or interchange ID.

## Import manifest

The published database path MUST contain a deterministic `ladybug-import-manifest.json` with at
least:

```json
{
  "bundle_manifest_sha256": "...",
  "bundle_schema_version": "1.1",
  "loader_schema_version": "1.0",
  "ladybug_version": "...",
  "cli_version": null,
  "configuration": {},
  "counts": {
    "nodes": 0,
    "relationships": 0,
    "instructions": 0
  },
  "source_files": {}
}
```

Values derived from wall-clock time, process IDs, temporary paths, or machine-specific locations
MUST NOT be included in the deterministic manifest. Run logs and resource measurements belong in
separate evidence artifacts.

## Publication and reuse

1. Resolve and validate the source bundle.
2. Compute the source/configuration identity.
3. Create a temporary database path outside source control.
4. Create the schema and import records in bounded batches.
5. Run integrity queries and write `ladybug-import-manifest.json`.
6. Close/checkpoint the database and atomically publish the complete database bundle.
7. On any failure, remove only the temporary staging path and retain the prior published bundle.

Warm reuse is valid only when the source manifest hash, bundle schema, loader schema, Ladybug
version, and configuration all match. A mismatch produces an explicit stale-artifact result and
requires an intentional rebuild.

## Query contract

The future application adapter exposes typed operations rather than arbitrary Cypher:

- exact lookup by stable source ID;
- filter by node `kind` or edge `type`;
- bounded neighbor traversal with an explicit maximum depth;
- full-text lookup over `search_text`;
- optional vector lookup over an embedding-bearing derived projection.

Every operation returns source IDs, authority/provenance fields, deterministic ordering keys, and a
status of `complete`, `partial`, `not_found`, or `unavailable`. A partial result MUST NOT be
consumed as complete evidence. Vector availability is reported separately from vector relevance.

All query exports used for determinism tests MUST include explicit `ORDER BY` clauses and stable
JSON serialization. Physical database bytes are not themselves a determinism contract.

## Failure and concurrency rules

- A checksum, schema, JSON, endpoint, or identity error prevents publication.
- A conflicting node ID is an error; an identical duplicate is idempotent.
- A duplicate relationship is retained only once when its complete canonical content is identical.
- A missing relationship endpoint is an explicit import failure, not an omitted edge.
- A stale or locked published database is not overwritten automatically.
- One process owns read/write publication; read-only consumers may share a valid published database
  only after the compatibility probe confirms that mode on the target environment.
- CLI and Python processes must not concurrently claim write ownership of the same database path.

## Evidence boundary

LadybugDB documentation and third-party articles establish hypotheses and operating constraints.
The project accepts the loader only after local evidence verifies package/CLI versions, Python and
Windows compatibility, import fidelity, deterministic queries, failure recovery, and resource
behavior. Producer DWARF facts remain authoritative throughout.

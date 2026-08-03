# Feature Specification: LadybugDB-first knowledge-graph loader

**Feature branch:** `015-ladybugdb-knowledge-graph`
**Task ID:** `KG-001`
**Status:** Draft; LadybugDB selected for compatibility and import evaluation
**Owner:** DDON DWARF Reconstructor maintainers

## Problem

The reconstructor already publishes a deterministic graph-shaped bundle, but it does not publish a
database or provide a graph query adapter. Earlier documentation named Neo4j as the implied future
backend even though the repository has no server dependency, database credentials, or live graph
contract. The next step must evaluate a local embedded backend against the existing evidence rules
before it becomes a runtime dependency.

LadybugDB is the proposed backend because its documented model is embedded and on-disk, its Python
client is installable with `uv`, and its standalone `lbug` shell provides a separate operational
surface. The [official installation documentation](https://docs.ladybugdb.com/installation/)
describes these surfaces. This specification treats those capabilities as external observations
until the local compatibility and import gates pass.

## Outcome

The repository shall have a versioned, provenance-preserving contract for loading the existing
JSONL knowledge bundle into a source-bound LadybugDB database. The JSONL bundle and its manifest
remain the canonical interchange artifact. A loader is a derived read model and MUST NOT alter,
replace, or reinterpret authoritative producer facts.

The feature remains a LadybugDB-first evaluation gate. No production dependency, live database,
graph API, or interactive graph browser is added until the acceptance evidence below is complete.

## Requirements

- **KG-001-01 Input binding:** The loader MUST accept an existing bundle through `manifest.json`,
  validate every declared file and SHA-256 checksum before opening a write transaction, and reject
  unsupported bundle schema versions or incomplete input with structured diagnostics.
- **KG-001-02 Canonical records:** `nodes.jsonl`, `relationships.jsonl`, and optional
  `instructions.jsonl` MUST remain byte-preserved source inputs. `reconstructed_cpp` and other
  manifest-declared artifacts MUST remain available through the source-bound import manifest.
- **KG-001-03 Ladybug schema:** The default evaluation schema MUST contain `KnowledgeNode`,
  `KnowledgeEdge`, and `KnowledgeInstruction` tables. Node IDs MUST reuse source node IDs;
  relationship and instruction IDs MUST be deterministic SHA-256 identifiers of their canonical
  JSON records. Heterogeneous properties MUST be stored as native JSON, with a fixed derived
  `search_text` projection for bounded textual lookup.
- **KG-001-04 Provenance:** Each imported record MUST retain its source bundle identity, producer,
  schema version, evidence status, authority, and source/tool provenance. Missing, partial,
  conflicting, duplicate, unavailable, cyclic, and timeout evidence MUST remain distinguishable.
- **KG-001-05 Import publication:** The loader MUST import into a temporary source-bound database
  path, write `ladybug-import-manifest.json`, close/checkpoint the database, and publish the
  complete database bundle atomically. A failed import MUST NOT replace a previous valid bundle or
  leave a partially published result.
- **KG-001-06 Warm reuse:** A reusable database MUST be keyed and validated by source manifest hash,
  bundle schema, loader schema, Ladybug version, and import configuration. Stale or mismatched
  artifacts MUST be rejected or explicitly rebuilt; they MUST NOT be silently reused.
- **KG-001-07 Typed query boundary:** The future application adapter MUST expose bounded typed
  operations for exact ID lookup, kind/type filtering, bounded neighbor traversal, and full-text
  search. It MUST return deterministic ordering and preserve `complete`, `partial`, `not_found`,
  and `unavailable` status semantics. Arbitrary Cypher MUST NOT become the domain contract.
- **KG-001-08 Optional vector stage:** Vector search MAY be enabled only when an embedding-bearing
  projection and the Ladybug vector extension are available. A bundle without embeddings MUST
  report vector search as `not_observed` or `unavailable`, not as a failed graph import.
- **KG-001-09 Concurrency:** The publication path MUST have one explicit write owner. Read-only
  consumers MAY open a published database concurrently when supported by LadybugDB, while a
  simultaneous write or CLI operation MUST produce a bounded lock diagnostic and leave the
  published artifact intact. The design follows the documented
  [LadybugDB connection and concurrency model](https://docs.ladybugdb.com/concurrency/).
- **KG-001-10 Compatibility gate:** The Python client MUST be tested with the repository's pinned
  CPython 3.14.6 environment and Windows acceptance environment. The standalone `lbug` CLI MUST be
  tested separately; the Python package MUST NOT be assumed to provide the CLI executable.
- **KG-001-11 Documentation evidence:** The feature MUST record exact LadybugDB, Python client,
  CLI, extension, operating-system, and configuration versions used by each acceptance run.
  Secondary articles MAY inform hypotheses but MUST NOT serve as implementation or performance
  acceptance evidence.

## Acceptance scenarios

1. A deterministic fixture bundle containing producer nodes, evidence nodes, instructions,
   relationships, null values, zero offsets, partial diagnostics, and duplicate/conflict cases is
   accepted or rejected according to the contract without loading the complete source into an
   unbounded in-memory structure.
2. A fresh-process import produces a source-bound `ladybug-import-manifest.json` whose counts,
   input hash, schema identity, and tool versions match the input and configuration.
3. A repeated import of the same bundle produces byte-identical canonical query exports and does
   not create a second logical copy of any source node or relationship.
4. Exact ID, typed filter, bounded neighbor, and full-text fixtures return stable ordered results
   with preserved provenance and status. Missing, partial, and unavailable stages remain explicit.
5. An optional embedding fixture exercises the vector extension; the base fixture reports vector
   availability accurately without requiring an external embedding model.
6. Malformed JSONL, checksum mismatch, unsupported schema, conflicting node identity, dangling
   endpoint, stale import manifest, interrupted write, failed extension load, and database-lock
   cases leave no newly published partial database and preserve any prior valid publication.
7. The Python package and standalone CLI probes record compatible versions or a concrete blocked
   prerequisite. A documented Python-wheel/CPython mismatch remains blocked rather than silently
   downgraded or bypassed.
8. Cold/warm import time, peak memory, database/WAL size, and representative query latency are
   recorded for the deterministic fixture. Real-asset and performance runs remain explicitly
   qualified environmental evidence.
9. The documentation build and repository quality checks pass, and source Markdown/specs contain
   no stale claim that Neo4j is the selected future backend.

## Non-goals

- Adding LadybugDB, `lbug`, a graph loader, a graph API, or a live database to the production
  runtime in this specification-update slice.
- Replacing the existing JSONL interchange contract or changing reconstruction semantics.
- Treating LadybugDB marketing claims, third-party benchmarks, or a successful package import as
  proof of graph-import correctness.
- Moving proprietary ELF/dump inputs, generated headers, credentials, runtime caches, or database
  files into source control.
- Preserving Neo4j-specific query syntax, server configuration, credentials, or deployment policy.

# Research: LadybugDB-first knowledge-graph loader

**Task ID:** `KG-001`
**Status:** Research baseline; compatibility and import gates remain open
**Evidence date:** 2026-08-03

## Decision context

LadybugDB is the selected direction for the next knowledge-graph evaluation. This is a proposed
derived read model, not a production dependency or a claim that the repository already imports a
live database. The canonical source remains the deterministic JSONL bundle and its manifest.

The relevant comparison is between an embedded, source-bound LadybugDB projection and the
previously implied server-oriented Neo4j target:

| Concern | LadybugDB-first direction | Superseded Neo4j assumption |
| --- | --- | --- |
| Deployment | Embedded Python client and on-disk database; standalone `lbug` for operations | Server/database-service deployment, credentials, and remote operational policy would have been required |
| Schema | Explicit node and relationship tables/types; schema must be created before import | Existing Neo4j-shaped assumptions cannot be copied without checking schema and Cypher differences |
| Import | Project the canonical JSONL bundle through a source-bound manifest and atomic publisher | No server bulk-import or Neo4j-specific loader contract is retained |
| Python and Windows | `uv add ladybug` is documented; Windows support and CPython 3.14.6 compatibility remain gates | No Neo4j Python/server dependency is added |
| CLI | `lbug` is a separately installed executable; the Python package is not assumed to expose it | No server CLI or credentials surface is required for this slice |
| Search | Full-text and vector stages are optional extensions with independent availability | No Neo4j-specific search or vector semantics become the domain contract |
| Licensing | Official Ladybug installation documentation identifies source and precompiled binaries as MIT | Neo4j licensing and edition terms are not carried into this proposal; any future comparison would require a fresh legal review |

The comparison is architectural, not a benchmark. No third-party article is used as acceptance
evidence.

## Primary evidence

- [Installation](https://docs.ladybugdb.com/installation/) documents an embedded graph database,
  a standalone `lbug` shell, Python installation through `uv add ladybug`, Windows CLI packages,
  and MIT licensing for source and precompiled binaries.
- [Python API](https://docs.ladybugdb.com/client-apis/python/) documents `Database` and
  `Connection` integration, including synchronous and asynchronous client surfaces.
- [System requirements](https://docs.ladybugdb.com/system-requirements/) documents Windows support
  for the CLI and precompiled Python wheels through CPython 3.11. The repository is pinned to
  CPython 3.14.6, so this is a compatibility gate rather than a satisfied prerequisite.
- [Cypher differences](https://docs.ladybugdb.com/cypher/difference/) confirms that Neo4j syntax
  and behavior cannot be treated as a drop-in schema/query contract.
- [Native JSON and JSON extension](https://docs.ladybugdb.com/extensions/json/) support retaining
  heterogeneous producer properties as JSON rather than flattening them into untyped strings.
- [Graph-database import guidance](https://docs.ladybugdb.com/import/graph-databases/) informs the
  import boundary, but it does not replace validation of this repository's manifest, provenance,
  duplicate, conflict, and dangling-endpoint rules.
- [Connections and concurrency](https://docs.ladybugdb.com/concurrency/) informs the one-writer,
  read-only sharing design and its environment-specific limitations.
- [Full-text search](https://docs.ladybugdb.com/extensions/full-text-search/) and
  [vector search](https://docs.ladybugdb.com/extensions/vector/) are independent extension stages;
  neither is required for the base graph import when embeddings are absent.
- [LadybugDB source repository](https://github.com/LadybugDB/ladybug) identifies the project as an
  embedded graph database with full-text and vector retrieval features and links its MIT license.

## Local exploratory probes

These probes were run outside the repository project environment and are observations only. They
do not add a dependency, change `pyproject.toml`, or satisfy the full KG-001 acceptance gate.

| Probe | Observation | Interpretation |
| --- | --- | --- |
| `uv run --no-project --python 3.14.6 --with ladybug python ...` | Resolved `ladybug` 0.19.0 and imported successfully under CPython 3.14.6 | Encouraging current-wheel signal, but it is not an exact pinned-package or full Windows acceptance run |
| `Database(":memory:")`, `Connection`, and `RETURN 1` | Completed successfully | Basic Python client/database/query surface is available in the probe environment |
| `INSTALL vector; LOAD vector; INSTALL fts; LOAD fts;` | Both extension stages loaded in the probe | Extension availability is technically observable; schema/index and query fidelity still require fixtures |
| `uvx --from ladybug lbug --version` | Failed because the Python package did not provide an executable | Confirms that `lbug` must be installed and verified separately |

The official Python compatibility statement and the local CPython 3.14.6 observation disagree in
scope. KG-001 therefore requires an exact package version, a fresh-process Windows run, and a
separately downloaded or package-managed `lbug` binary before implementation proceeds.

## Evidence classification

- **Confirmed from primary documentation:** embedded/on-disk deployment model, separate CLI and
  Python installation surfaces, explicit schema requirement, native JSON, FTS/vector extension
  boundaries, concurrency model, Windows CLI availability, documented Python wheel range, and MIT
  licensing.
- **Locally observed but not accepted:** `ladybug` 0.19.0 import under CPython 3.14.6, basic query
  execution, and extension loading.
- **Blocked or remaining:** exact version pin and reproducibility, standalone `lbug` version and
  JSONL output, Windows read-only/multi-process behavior, import fidelity for all fixture cases,
  atomic publication/rollback, stale-cache rejection, deterministic queries, and resource metrics.
- **Secondary context only:** the supplied Consensus and Medium articles may guide workload and
  hybrid graph/vector hypotheses, but their code, measurements, and compatibility statements are
  not acceptance evidence.

## Research consequences

1. Keep the JSONL bundle and manifest canonical; do not make the database bytes the determinism
   contract.
2. Define explicit `KnowledgeNode`, `KnowledgeEdge`, and `KnowledgeInstruction` tables and retain
   canonical JSON properties plus deterministic derived search text.
3. Treat LadybugDB schema and Cypher differences as adapter concerns; expose typed bounded queries
   instead of arbitrary Cypher to the application.
4. Gate FTS and vector search independently. Missing embeddings report unavailable or
   not-observed vector capability without invalidating the base import.
5. Require source-bound manifests, atomic staging/publication, one write owner, read-only sharing
   evidence, and explicit rollback before any production integration is proposed.

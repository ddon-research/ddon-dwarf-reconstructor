# Export the knowledge graph

The exporter projects deterministic producer evidence into a portable graph-shaped bundle. The
current contract is JSON Lines plus a manifest, not a live Neo4j service. That keeps the export
bounded, reviewable, and usable by downstream graph loaders without making graph infrastructure
a requirement for reconstruction.

```powershell
uv run ddon-dwarf-reconstructor export-knowledge `
  resources/DDOORBIS.elf `
  --symbol rLayout `
  --output-dir output/knowledge/rLayout
```

The command writes deterministic `nodes.jsonl`, `relationships.jsonl`, `instructions.jsonl`, a
`reconstructed_cpp` projection, and a manifest. The exact option surface is available through:

```powershell
uv run ddon-dwarf-reconstructor export-knowledge --help
```

## Evidence rules

- The owning DIE is the authority for a producer fact.
- Cross-producer or external-tool observations are additive provenance.
- Missing output is `not_observed`, not proof that the producer lacks the fact.
- Incomplete, conflicting, duplicate, unavailable, cyclic, and timeout evidence remains explicit.

This is the bridge between the reconstructor and a future searchable knowledge graph. See the
[knowledge graph contract](../reference/knowledge-graph.md) for the node/edge model and the
[roadmap](../roadmap/index.md) for the missing live-ingestion and visualization layer.

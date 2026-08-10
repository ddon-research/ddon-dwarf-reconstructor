# Export the knowledge graph

The exporter projects deterministic producer evidence into a portable graph-shaped bundle. The
current contract is JSON Lines plus a manifest, not a live LadybugDB database or service. That keeps the export
bounded, reviewable, and usable by downstream graph loaders without making graph infrastructure
a requirement for reconstruction.

Knowledge export uses the same Doris-backed runtime as header generation. First materialize and
publish a complete source-bound analytical store, then pass its manifest with `--dwarf-store`:

```powershell
$storeRoot = Join-Path $PWD 'output\analytical-dwarf\main'
uv run ddon-dwarf-reconstructor artifacts materialize-dwarf `
  resources/DDOORBIS.elf --output-dir $storeRoot --write-parquet
$storeManifest = Join-Path $storeRoot 'store-<source-sha16>\manifest.json'
uv run ddon-dwarf-reconstructor artifacts load-doris $storeManifest
```

```powershell
uv run ddon-dwarf-reconstructor export-knowledge `
  resources/DDOORBIS.elf `
  --dwarf-store $storeManifest `
  --symbol rLayout `
  --output-dir output/knowledge/rLayout
```

The command writes deterministic `nodes.jsonl`, `relationships.jsonl`, `instructions.jsonl`, a
`reconstructed_cpp` projection, and a manifest. The exact option surface is available through:

```powershell
uv run ddon-dwarf-reconstructor export-knowledge --help
```

The export fails closed when the Doris publication is unavailable, stale, incomplete, or has
family counts that do not match the manifest. It does not reopen the ELF or read Parquet/JSONL as
a runtime fallback.

## Evidence rules

- The owning DIE is the authority for a producer fact.
- Cross-producer or external-tool observations are additive provenance.
- Missing output is `not_observed`, not proof that the producer lacks the fact.
- Incomplete, conflicting, duplicate, unavailable, cyclic, and timeout evidence remains explicit.

This is the bridge between the reconstructor and a future searchable knowledge graph. See the
[knowledge graph contract](../reference/knowledge-graph.md) for the node/edge model and the
[roadmap](../roadmap/index.md) for the missing live-ingestion and visualization layer. The
LadybugDB-first loader contract is tracked in
[`KG-001`](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/015-ladybugdb-knowledge-graph).

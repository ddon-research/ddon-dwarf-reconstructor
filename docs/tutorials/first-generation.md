# First generation

This tutorial walks through the smallest useful reconstruction run. It assumes the repository
has been synchronized with CPython 3.14.7 and that the local ELF is available. Real inputs are
large and proprietary; keep their paths local and do not commit generated outputs.

## 1. Install the locked environment

```powershell
uv sync --python 3.14.7 --locked
```

## 2. Inspect the command tree

```powershell
uv run ddon-dwarf-reconstructor --help
uv run ddon-dwarf-reconstructor generate --help
```

The root entry point has three intentional command groups: `generate`, `export-knowledge`, and
`artifacts`.

## 3. Materialize the analytical store

The first materialization is the one intentionally expensive CU traversal. Put durable output in
the ignored repository store and reuse the resulting manifest:

```powershell
$storeRoot = Join-Path $PWD 'output\analytical-dwarf\main'
uv run ddon-dwarf-reconstructor artifacts materialize-dwarf `
  resources/DDOORBIS.elf `
  --output-dir $storeRoot
```

## 4. Generate one symbol

```powershell
uv run ddon-dwarf-reconstructor generate `
  resources/DDOORBIS.elf `
  --dwarf-store (Join-Path $storeRoot 'store-<source-sha16>\manifest.json') `
  --symbol MtObject `
  --output output/first-generation
```

The application opens one `ElfDwarfSession`, resolves the requested definition through the
domain ports, and publishes generated headers atomically with a byte/size/SHA-256 manifest.

## 5. Check the result

```powershell
Get-ChildItem output/first-generation -Recurse
Get-Content output/first-generation/header-bundle.manifest.json
```

Treat the manifest as the stable handoff artifact. If evidence is incomplete, the result must
remain visibly incomplete; do not fill missing offsets, methods, or types with guesses.

For the full season-two list, use `--symbols-file resources/season2-resources.txt` with
`--full-hierarchy`. Multiple roots publish separate, atomically replaced bundles under the
`symbols/` subdirectory, so same-named headers cannot silently overwrite one another. Check each
bundle manifest and the generation report before claiming corpus completion.

## 6. Continue from here

- Need a hierarchy: [Generate headers](../how-to/generate-headers.md).
- Need graph-shaped evidence: [Export the knowledge graph](../how-to/export-knowledge-graph.md).
- Need to diagnose a cache or dump: [Inspect durable artifacts](../how-to/inspect-artifacts.md).
- Need to change the implementation: [Validate changes](../how-to/validate-changes.md).

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

The application opens one `ElfDwarfSession`, resolves the requested symbol and its complete
dependency closure through the domain ports, and publishes a flat versioned directory. Context
generation is enabled by default, so the manifest is available for development inspection.

## 5. Check the result

```powershell
Get-ChildItem output/first-generation -Recurse
Get-Content output/first-generation/ps4-unknown/symbols.manifest.json
```

Treat the manifest as the stable handoff artifact. If evidence is incomplete, the result must
remain visibly incomplete; do not fill missing offsets, methods, or types with guesses.

For the full season-two list, use `--symbols-file resources/season2-resources.txt`. The same
symbol workflow performs one union traversal for the list and one atomic publication under
`generated/ps4-<client-version>/` (or the explicit `--output` root):

```text
generated/ps4-<client-version>/
  symbols.manifest.json      # with the development default --generate-context
  shared/<dependency>.h
  <resource-class>/<resource>.h
  <resource-class>/<owner>-<method>-<stable-hash>.asm
```

The manifest is the symbol-set handoff: check its input-list/source identity, ownership, hashes,
per-root statuses, and unresolved/conflict diagnostics. A single `--symbol` uses the same flat
layout. Use `--no-generate-context` for a clean headers/assembly-only handoff; it omits all
generation-context JSON. No `symbols/`, `implementations/`, or `methods/<id>/` directories are
created.

## 6. Continue from here

- Need a hierarchy: [Generate headers](../how-to/generate-headers.md).
- Need graph-shaped evidence: [Export the knowledge graph](../how-to/export-knowledge-graph.md).
- Need to diagnose a cache or dump: [Inspect durable artifacts](../how-to/inspect-artifacts.md).
- Need to change the implementation: [Validate changes](../how-to/validate-changes.md).

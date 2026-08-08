# Generate headers

Use the canonical Typer entry point for reconstruction. The launcher is intentionally thin; the
application layer receives typed requests and the composition root wires concrete infrastructure.

## Single or multiple symbols

Materialize the ELF once before the first generation run. Keep the durable store in the ignored
repository output area so subsequent runs reuse the source-bound manifest:

```powershell
$storeRoot = Join-Path $PWD 'output\analytical-dwarf\main'
uv run ddon-dwarf-reconstructor artifacts materialize-dwarf `
  resources/DDOORBIS.elf `
  --output-dir $storeRoot
```

```powershell
$storeManifest = Join-Path $storeRoot 'store-<source-sha16>\manifest.json'
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf `
  --dwarf-store $storeManifest `
  --symbol MtObject
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf `
  --dwarf-store $storeManifest `
  --symbol MtObject --full-hierarchy
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf `
  --dwarf-store $storeManifest `
  --symbols-file resources/season2-resources.txt
```

`--symbol` is repeatable for targeted work. Do not combine it with `--symbols-file`; the CLI
rejects the ambiguous request. Use `--full-hierarchy` only when inherited definitions and their
dependencies are part of the requested evidence surface.

When `--symbols-file` requests more than one full-hierarchy root without `--single-file`, the
workflow publishes separate bundles under `output/season2/<platform>/symbols/<index>-<safe-root>/`.
Each bundle has its own `header-bundle.manifest.json`; the root index and symbol name remain in
the manifest metadata. This avoids overwriting same-named headers from unrelated roots. Aggregate
single-directory publication still fails closed when two roots produce conflicting file contents.
Keep failed or incomplete root status in the run report rather than treating the surviving bundles
as a complete corpus.

## What happens inside

1. `DwarfGeneratorSetup` opens the validated source-bound store session and its query/index ports.
2. `DwarfGenerator` resolves definitions, types, methods, members, and hierarchy information
   from materialized records; it does not implicitly traverse the ELF.
3. `HeaderGenerator` renders deterministic declarations with stable ordering and forward
   declarations where required.
4. `AtomicHeaderPublisher` stages the bundle, writes its manifest, and commits or rolls back as a
   unit.

The implementation preserves qualified names, inheritance, field offsets, sizes, source
locations, DIE/CU provenance, and deterministic output ordering. A partial search result is not
complete evidence and must not be consumed as if it were.

## Useful output controls

Use `uv run ddon-dwarf-reconstructor generate --help` for the installed option surface. Keep
generated headers and manifests under `output/` or another explicitly local directory. The
repository does not accept game binaries, generated headers, or runtime caches as source files.

## Troubleshooting order

1. Run `artifacts inspect-dwarf-store <manifest>` to validate the store and source binding.
2. Run `artifacts inspect-elf <path>` to confirm the ELF/DWARF producer facts.
3. Check the run JSONL logs for the `run_id`, symbol, stage, and query evidence status.
4. If a compressed dump is involved, use `artifacts inspect-dwarf-dump <path>` only for an
   explicitly labeled validation cross-check.

Do not delete a warm source-bound cache as routine cleanup. Repair and purge commands are
explicit and narrowly targeted.

# Generate headers

Use the canonical Typer entry point for reconstruction. The launcher is intentionally thin; the
application layer receives typed requests and the composition root wires concrete infrastructure.

## Single or multiple symbols

```powershell
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol MtObject
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol MtObject --full-hierarchy
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbols-file resources/season2-resources.txt
```

`--symbol` is repeatable for targeted work. Do not combine it with `--symbols-file`; the CLI
rejects the ambiguous request. Use `--full-hierarchy` only when inherited definitions and their
dependencies are part of the requested evidence surface.

## What happens inside

1. `DwarfGeneratorSetup` creates one session and its source-bound index services.
2. `DwarfGenerator` resolves definitions, types, methods, members, and hierarchy information
   through domain ports.
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

1. Run `artifacts inspect --elf <path>` to see catalog, cache, and dump-index state.
2. Run `artifacts inspect-elf <path>` to confirm the ELF/DWARF producer facts.
3. Check the run JSONL logs for the `run_id`, symbol, stage, and cache decision.
4. If a compressed dump is involved, use `artifacts inspect-dwarf-dump <path>` before rebuilding
   its index.

Do not delete a warm source-bound cache as routine cleanup. Repair and purge commands are
explicit and narrowly targeted.

# Configuration and paths

The root project is pinned to CPython `3.14.6`. Install it with:

```powershell
uv sync --python 3.14.6
```

The optional Nuitka build uses the same regular CPython environment and publishes its onefile
output under the OS-local performance artifact directory (on Windows, normally
`C:\Users\<user>\AppData\Local\ddon-dwarf-reconstructor\performance\nuitka\`). Free-threaded
CPython comparisons use a separate `UV_PROJECT_ENVIRONMENT` venv; never replace the root `.venv`
or pass a bare interpreter that does not contain the project installation.

The nested `tools/dwarf_spec_pipeline` project is independent and must be invoked with
`uv run --directory tools/dwarf_spec_pipeline ...`.

## Durable local paths

| Path | Role | Source-control policy |
| --- | --- | --- |
| `output/` | generated headers, manifests, tool exports, logs | ignored |
| `output/analytical-dwarf/main/` | durable source-bound analytical stores, including the promoted `store-<source-sha16>` directory | ignored; retain locally as evidence |
| `.dwarf_cache/` | local symbol/cache state | ignored |
| `resources/.cache/` | explicit checked-in or local acceptance indexes | preserve source-bound entries |
| `docs/knowledge-base/dwarf-specification/generated/` | checked-in generated DWARF artifacts | deterministic, validated source |
| `site/` | Zensical build output | ignored |

Do not put ELF files, expanded dumps, generated headers, credentials, or runtime caches into
`specs/` or the published site. Use explicit local paths for real-asset and performance evidence.
The durable analytical-store path is under `output/analytical-dwarf/main/`; `%TEMP%\ddon-analytical-dwarf`
is for disposable checkpoints, bounded probes, profiler output, and crash diagnostics only. Do not
promote a Temp run directory or a versioned database name to the canonical store identity.

## Environment and logging

Runtime configuration is typed under `infrastructure/configuration.py`. Keep diagnostics on stderr
and JSONL logs; reserve stdout for structured artifact output. Langfuse credentials belong in
`ops/langfuse/.env` or the user-level Codex configuration described by its integration guide.

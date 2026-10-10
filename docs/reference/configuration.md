# Configuration and paths

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](project-status.md).

The root project is pinned to CPython `3.14.7` and uv `0.12.3`. Install it with:

```powershell
uv sync --python 3.14.7 --locked
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

## Environment configuration and `.env`

Runtime configuration is typed under
`src/ddon_dwarf_reconstructor/infrastructure/config/application_config.py` for general application
settings and `src/ddon_dwarf_reconstructor/infrastructure/analytical/doris_config.py` for Doris
serving and warehouse options.

The application automatically loads `.env` from the current working directory on startup via
`Config.from_env()`. A template file `.env.template` is provided in the repository root. Copying
this template to `.env` allows developers to set stable local paths (ELF file, SDK toolchain,
Doris endpoints, store manifest) once, eliminating the need to pass repetitive path arguments on
the command line. Explicit CLI options always override values defined in `.env` or the environment.

### Application settings

| Variable | Description | Default |
| --- | --- | --- |
| `ELF_FILE_PATH` | Path to the PS4 ELF file containing DWARF debug information | `resources/DDOORBIS.elf` |
| `OUTPUT_DIR` | Output directory for reconstructed C++ headers and reports | `output` |
| `VERBOSE` | Enable debug logging on stderr (`true`/`false`) | `false` |
| `LOG_DIR` | Directory for structured JSONL diagnostics | `logs` |
| `DWARF_STORE_MANIFEST` | Pre-materialized DWARF analytical store manifest path (fallback: `DDON_DWARF_STORE`) | `None` |
| `ORBIS_OBJDUMP_PATH` | Path to the `orbis-objdump.exe` binary (fallback: `ORBIS_OBJDUMP`) | `None` |
| `ORBIS_AS_PATH` | Path to the `orbis-as.exe` binary (fallback: `ORBIS_AS`) | `None` |
| `LLVM_READOBJ_PATH` | Path to `llvm-readobj.exe` for generic ELF verification (fallback: `LLVM_READOBJ`) | `None` |
| `LLVM_OBJDUMP_PATH` | Path to `llvm-objdump.exe` for structural disassembly cross-checks (fallback: `LLVM_OBJDUMP`) | `None` |

### Doris analytical warehouse settings

The application queries Doris directly during generation and knowledge export. The canonical
Docker Compose configuration in `ops/analytical-dwarf/compose.yaml` maps the container ports
to dedicated host ports on the development workstation.

| Variable | Description | Canonical workstation mapping | Container default |
| --- | --- | --- | --- |
| `DDON_DORIS_SQL_HOST` | Doris Frontend MySQL protocol host | `127.0.0.1` | `127.0.0.1` |
| `DDON_DORIS_SQL_PORT` | Doris Frontend MySQL protocol port | `29030` | `9030` |
| `DDON_DORIS_HTTP_URL` | Doris Frontend HTTP URL for metadata and schema queries | `http://127.0.0.1:28030` | `http://127.0.0.1:8030` |
| `DDON_DORIS_STREAM_LOAD_URL` | Doris Backend HTTP URL for streaming Parquet loads | `http://127.0.0.1:28040` | `http://127.0.0.1:8040` |
| `DDON_DORIS_DATABASE` | Target database for analytical DWARF tables | `dwarf` | `dwarf` |
| `DDON_DORIS_USER` | MySQL user for database operations | `root` | `root` |
| `DDON_DORIS_PASSWORD` | MySQL password for the specified user | `""` | `""` |
| `DDON_DORIS_TABLE` | Base record table name | `dwarf_records` | `dwarf_records` |
| `DDON_DORIS_SERVING_VARIANT_ID` | Analytical serving layout variant | `canonical` | `canonical` |
| `DDON_DORIS_ANALYZE_AFTER_LOAD` | Run `ANALYZE TABLE` automatically after stream loading | `true` | `true` |
| `DDON_DORIS_ANALYZE_WAIT_SECONDS` | Seconds to wait for asynchronous analyze completion (`0` disables waiting) | `0.0` | `0.0` |
| `DDON_DORIS_STREAM_LOAD_WORKERS` | Concurrent HTTP workers for stream load batches | `1` | `1` |

Flight SQL benchmark configuration is also environment-driven via `DDON_DORIS_FLIGHT_SQL_HOST`
(`127.0.0.1`), `DDON_DORIS_FLIGHT_SQL_PORT` (`8070`), and related options.

## Logging and developer tracing

Runtime diagnostics are written to JSONL files under `logs/` and human-readable progress is
streamed to stderr. Reserve stdout for structured artifact output (such as JSON reports from
artifact commands). Langfuse credentials belong in `ops/langfuse/.env` or the user-level Codex
configuration described by its integration guide.

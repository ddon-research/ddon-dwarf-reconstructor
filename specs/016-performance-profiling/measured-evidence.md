# Measured evidence: Source-bound profiling and benchmark history

This record separates deterministic fixture evidence from environmental real-asset evidence. It is
updated only from named commands and retained manifests.

## Deterministic evidence

| Command | Status | Evidence |
| --- | --- | --- |
| `uv run pytest tests/domain/models/test_performance.py tests/infrastructure/test_performance_runner.py tests/infrastructure/test_performance_history.py tests/infrastructure/test_performance_workloads.py tests/performance/test_fixture_benchmark.py -q` | observed | fixture, timeout, schema, export, and command-construction tests |
| `uv run just test-performance-fixtures` | observed | deterministic fixture resource budget passed |

## Validation

| Command | Status | Evidence |
| --- | --- | --- |
| `uv run just test-unit` | observed | 457 passed, 7 deselected |
| `uv run just check` | observed | Ruff, actionlint 1.7.12, Pyrefly, deptry, structure, architecture, and docs gates passed |
| `uv run just test` | observed | 459 passed, 5 deselected |
| `uv run just coverage-ci` | observed | 82.43% total; named groups met line/branch thresholds |
| `uv run just audit` | observed | Prospector reported 0 findings |
| `uv run just docs-check` | observed | Markdownlint, 13 Mermaid diagrams, and strict Zensical build passed |
| `uv run --directory tools/dwarf_spec_pipeline just test` | observed | 17 passed, 1 deselected |
| `uv run --directory tools/dwarf_spec_pipeline just check` | observed | Ruff, Pyrefly, and deptry passed |
| `uv run just package` and `uv run just package-smoke` | observed | wheel/sdist built; packaging smoke passed |

## Environmental evidence

| Profile | Inputs | State | Status | Raw manifest |
| --- | --- | --- | --- | --- |
| warm `rLayout` export: Scalene | explicit local ELF and source-bound index | warm | observed; 4.746 s, peak RSS 1,720,025,088 B | `C:\Users\morph\AppData\Local\ddon-dwarf-reconstructor\performance\warm-rlayout\02d8c7a585994088b7931f53761ca6d2\manifest.json` |
| warm `rLayout` export: cProfile | explicit local ELF and source-bound index | warm | observed; 4.554 s, peak RSS approximately 1.28 GiB | `C:\Users\morph\AppData\Local\ddon-dwarf-reconstructor\performance\warm-rlayout\485e36cb9496484a826ae96ea4f9e791\manifest.json` |
| warm `rLayout` export: pyinstrument | explicit local ELF and source-bound index | warm | observed; 4.346 s, peak RSS approximately 1.41 GiB | `C:\Users\morph\AppData\Local\ddon-dwarf-reconstructor\performance\warm-rlayout\8012b6bcc0bf45378849cd8c5a4862bb\manifest.json` |
| warm `rLayout` export: tracemalloc | explicit local ELF and source-bound index | warm | observed; 44.480 s, traced peak 2,091,626,645 B | `C:\Users\morph\AppData\Local\ddon-dwarf-reconstructor\performance\warm-rlayout\a7b0cf58033a44289b836e955960be2d\manifest.json` |
| warm `rLayout` export: py-spy | explicit local ELF and source-bound index | warm | partial; exit 1 and no Speedscope output on Windows | `D:\ddon-perf-artifacts\profiles\warm-rlayout-py-spy\8ba8e7d1fb7d43bd993e9e5b6a5cea58\manifest.json` |
| compressed-dump index construction | explicit local `.zst` dump and new sidecar path | cold | observed; 275.139 s, peak RSS 807,493,632 B, 11,437,217,487 B read, 9,569,041,641 B written | `D:\ddon-perf-artifacts\profiles\cold-dump-index-rebuild\1ecd2a0afc7d4755a65d036876d0d8bf\manifest.json` |

Unavailable tools, access-denied profilers, and missing assets remain status-bearing rows in the
SQLite ledger; they are not treated as successful substitutes. An earlier two-second cold export
invocation is excluded from the index-construction baseline because it reused an existing
source-bound cache and did not publish the requested sidecar. The cold sidecar produced by the
rebuild is 206,422,016 bytes and remains outside Git.

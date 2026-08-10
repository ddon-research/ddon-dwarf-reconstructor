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
| `uv run just test-unit` | observed | 606 passed, 7 deselected |
| `uv run just check` | partial | Ruff, actionlint 1.7.12, Pyrefly, deptry, architecture, and docs stages passed; the existing structure stage reports six violations in `jsonl_store.py`, `parquet_store.py`, and `main.py` |
| `uv run just test` | observed | 608 passed, 5 deselected |
| `uv run just coverage-ci` | observed | 80.74% total; named groups met line/branch thresholds |
| `uv run just audit` | observed | Prospector reported 0 findings |
| `uv run just docs-check` | observed | Markdownlint, 14 Mermaid diagrams, and strict Zensical build passed |
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

## Linux container evidence

The following rows are environmental evidence from the pinned `ddon-reconstructor:py3.14.6-uv0.12.1`
image on Linux 5.15 under Docker Desktop/WSL2. The source-bound analytical store is the complete
`4236f598acc8f158` store: 2,305 CUs, 95,540,741 DIEs, schema 1.1, and zero parser diagnostics.
The Linux rows are not Windows baselines because the serving-backend path, filesystem boundary, and
machine profile differ.

| Surface | Status | Observation | Raw artifact |
| --- | --- | --- | --- |
| image and smoke checks | observed | CPython 3.14.6, uv 0.12.1, Scalene 2.3.0, cProfile, pyinstrument 5.1.3, py-spy 0.4.2, pyperf 2.10.0, and psutil available | `D:\ddon-dwarf-reconstructor\ops\reconstructor\images.lock.json` |
| deterministic fixture | observed | 83.337 s process run, 126,382,080 B peak RSS, 1,645 samples; pyperf mean approximately 2.249 s | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\fixture-linux\fixture\3be2150ea0f243c2b4b10f92d5821eaa\manifest.json` |
| complete store verification | observed | source SHA-256 `4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`; complete manifest and mounted-ELF identity match | `D:\ddon-dwarf-reconstructor\output\analytical-dwarf\main\store-4236f598acc8f158\manifest.json` |
| default `host.docker.internal` Doris route | partial | SQL connection returned Linux `Network is unreachable` for the host-published endpoint; the shared `doris` network profile resolved FE/BE and connected to FE SQL successfully | `D:\ddon-dwarf-reconstructor\ops\reconstructor\compose.yaml` |
| warm export through shared Doris network | observed | 425.526 s wall, 23.87 s process CPU, 182,468,608 B peak RSS, 2,123 samples | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\linux-warm-process-doris\linux-warm-process-doris\5e255af935464c1a8ce815058c34a24e\manifest.json` |
| bounded native-Doris query, process sampler | observed | 116.616 s wall, 12.60 s process CPU, 173,445,120 B peak RSS, 582 samples; store load 59.797 s and Doris query 1.221 s | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\linux-doris-query-process-v2\analytical-dwarf-store-profile\28d3c98962dc40008b55061295d265ab\manifest.json` |
| bounded native-Doris query, cProfile | observed | 116.408 s; 71.1 s cumulative in `posix.lstat` reached through repeated `Path.resolve()` calls from manifest Parquet-file validation | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\linux-doris-query-cprofile\analytical-dwarf-store-profile\385372d33be4489dbcbff252a3a46f6a\cprofile.prof` |
| bounded native-Doris query, pyinstrument | observed | 63.095 s in analytical-store loading, including 34.518 s in manifest validation and 30.798 s in artifact measurement | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\linux-doris-query-pyinstrument\analytical-dwarf-store-profile\d937878068754dfa8714d984a2b01c4d\pyinstrument.json` |
| bounded native-Doris query, py-spy at 5 Hz | observed | 160 samples, zero errors, with `load_analytical_store`, `validate_manifest_files`, `declared_parquet_files`, and `resolve` frames; direct blocking trace | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\linux-doris-query-py-spy-lowrate.speedscope.json` |
| bounded native-Doris query, py-spy nonblocking at 5 Hz | observed with sampling errors | 152 samples and four errors; completed in approximately 125.5 s and retained the same validation frames | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\linux-doris-query-py-spy-nonblocking.speedscope.json` |
| canonical `profile-dwarf-store`, py-spy nonblocking at 5 Hz | observed | 115.067 s, 6.34 s user CPU, 22.82 s system CPU, 176,046,080 B peak RSS, 574 process samples; 125 speedscope samples with reconstructor file/line frames | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\linux-doris-query-py-spy-canonical-v2\analytical-dwarf-store-profile\8b302f6de4f74e5c92d2c730fb1afe01\manifest.json` |
| bounded native-Doris query, Scalene | partial attribution | JSON was written, but 99.3% was assigned to the launcher and only four import lines had non-zero non-wrapper attribution; no actionable reconstructor hot line | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\linux-doris-query-scalene\analytical-dwarf-store-profile\e1edc79f943f464aad651e2d17eb2cac\scalene.json` |
| Scalene scope matrix: `--profile-all` plus package filter and wrapper exclusion | observed | 70 non-zero package rows, no wrapper rows, and `manifest.py` validation lines; 17,252,934 B JSON | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\scalene-matrix\real-profile-all-only-exclude-wrapper.json` |
| Scalene scope matrix: same scope plus `--cpu-only` | observed | 38 non-zero package rows, no wrapper rows, the same leading `manifest.py` lines, and 10,904,568 B JSON; memory rows are intentionally absent | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\scalene-matrix\real-profile-all-only-exclude-wrapper-cpu-only.json` |
| Scalene scope matrix: package-root `--program-path` plus wrapper exclusion | observed | 73 non-zero package rows, no wrapper rows, default library exclusion retained, and 17,963,163 B JSON | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\scalene-matrix\real-program-path.json` |
| canonical `profile-dwarf-store`, scoped Scalene adapter | observed | 138.001 s, return code 0, 20 normalized method summaries, 68 non-zero raw package rows, no wrapper rows, source identity `4236f598acc8f158...`, Scalene 2.3.0 | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\linux-doris-query-scalene-scoped\analytical-dwarf-store-profile\519970b280b0416d8ffed55d77f8a3f6\manifest.json` |
| scoped Scalene plus explicit experimental leak detector | observed | 73 non-zero rows, 18,513,844 B JSON, `scalene_leak_records=0`, empty per-file `leaks` maps, maximum footprint 62.48 MB at `benchmark.py:440`; no likely leak record | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\scalene-matrix\real-scoped-leak-detector.json` |
| `--profile-system-libraries` without `--profile-all` | observed but ineffective for library scope | 70 non-zero rows and no external library files; current upstream exclusion order still filtered system paths | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\scalene-matrix\real-library-inclusive-leak-detector.json` |
| broad Scalene library view plus explicit leak detector | observed | 78 non-zero rows across 11 files, 30,794,564 B JSON, `scalene_leak_records=0`, `threading.py:1024` at 6.06% external CPU, `pathlib` at 1.10%, `pyarrow/dataset.py` present but small, empty per-file `leaks` maps | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\scalene-matrix\real-library-all-leak-detector.json` |
| canonical `profile-dwarf-store`, `scalene-libraries` alias | observed | 134.331 s wall, 0.56 s process CPU, 462,946,304 B peak RSS, 1,336 samples, 20 normalized library/application summaries, `scalene_leak_records=0`; top external rows remained `threading.py:1024` at 6.05% and `pathlib:938` at 1.03% | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\scalene-libraries-canonical\analytical-dwarf-store-profile\5bd5676f33944fa7864dc653da32959f\manifest.json` |
| py-spy at its 100 Hz default | partial | profiler consumed approximately one CPU for nearly eight minutes and did not finalize a speedscope file; the disposable container was stopped | no finalized artifact |

### Toolchain upgrade revalidation (2026-08-09)

These additive rows validate the upgraded container; the 3.14.6/uv 0.12.1 rows above remain
historical evidence. The no-cache build used the pinned Linux/amd64 Python and uv digests in
`ops/reconstructor/images.lock.json`.

| Surface | Status | Observation | Raw artifact |
| --- | --- | --- | --- |
| image and smoke checks | observed | Python 3.14.7, uv 0.12.3, CLI help, and `performance doctor` passed; Scalene 2.3.0, cProfile, pyinstrument 5.1.3, py-spy 0.4.2, pyperf 2.10.0, and psutil 7.2.2 were observed | `D:\ddon-dwarf-reconstructor\ops\reconstructor\images.lock.json` |
| deterministic fixture | observed | 88.168 s wall, 128,794,624 B peak RSS, 1,738 samples, return code 0; pyperf mean 2.388 s under CPython 3.14.7 | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\fixture\fixture\59a6da41c732495782e8e7356e8b1723\manifest.json` |
| final fixture after analytical runtime promotion | observed | 89.446 s wall, 127,766,528 B peak RSS, 1,763 samples, return code 0; pyperf mean 2.428 s under CPython 3.14.7 with the default analytical runtime installed | `D:\ddon-dwarf-reconstructor\output\reconstructor-linux\profiles\fixture-final\fixture\72ffa9a564b248a5a8d625f4dc9eb3a6\manifest.json` |

## Linux observations and action items

| Priority | Action | Evidence boundary and acceptance condition |
| --- | --- | --- |
| P0 | Measure a source-bound validation reuse path or a native-Linux-volume A/B before changing manifest validation. | cProfile, pyinstrument, and py-spy agree that repeated metadata/path validation dominates this bounded run. Preserve complete-manifest hashes, footer checks, source identity, and fail-closed behavior; a bind mount versus native volume comparison must separate Docker filesystem cost from Python policy cost. |
| P1 | Keep the py-spy adapter at nonblocking 5 Hz for CPython 3.14 container runs and retain the default-rate failure as environmental evidence. | The direct 5 Hz trace completed with zero errors and reconstructor frames; the nonblocking adapter-compatible trace completed with four sampling errors; the 100 Hz run did not publish output. Re-test if the py-spy or CPython version changes. |
| P1 | Keep the Scalene module-wrapper scope at package-root `--program-path` plus `--profile-exclude scalene_target.py`; use `--cpu-only` only for CPU-only investigations. | The Linux matrix recovered 73 package rows with no wrapper rows and retained the same validation hotspots; the broader `--profile-all` plus package filter also worked but is a diagnostic fallback. Re-run the scoped command on Windows before attributing the original loss to a CPython platform bug. |
| P1 | Keep `--profiler scalene-libraries` as an optional dependency-alternative diagnostic, not as the normal or `all` profile. | The broad run exposed standard-library frames, especially `threading.py` and `pathlib`, but did not displace the application validation hotspots; the narrower `--profile-system-libraries` flag alone was ineffective under the current upstream filter order. |
| P1 | Keep cProfile as an explicit deterministic cross-check. | It exposed 104,672 `posix.lstat` calls and 71.099 s self time through repeated `Path.resolve()` calls, a call-count/native-builtin surface not reproduced exactly by Scalene. |
| P2 | Use the explicit Scalene leak detector for repeated/long-lived workloads before making leak claims. | The one-iteration application and broad library profiles both had empty `leaks` maps; observed growth rate and maximum footprint remain allocation-growth signals, not confirmed leaks. |
| P2 | Use `py-spy dump --pid` for live point-in-time snapshots and retain `record` for bounded time-series samples. | The upstream tool supports external `dump` without restarting the process; the repository's 5 Hz nonblocking record remains the repeatable wall-clock/frame cross-check. |
| P1 | Capture Doris FE/BE `EXPLAIN` and profile records for the broad export. | The broad export was wall-time heavy but process-CPU light, while the bounded Doris query itself was 1.221 s. No database index or query redesign is justified until backend operator evidence exists. |
| P2 | Run exact output-manifest comparison for the same workload on Windows and Linux. | This turn established Linux completion and source identity, but did not produce a cross-platform hash comparison; output equivalence remains not observed. |

Unavailable tools, access-denied profilers, and missing assets remain status-bearing rows in the
SQLite ledger; they are not treated as successful substitutes. An earlier two-second cold export
invocation is excluded from the index-construction baseline because it reused an existing
source-bound cache and did not publish the requested sidecar. The cold sidecar produced by the
rebuild is 206,422,016 bytes and remains outside Git.

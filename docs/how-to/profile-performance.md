# Profile the application

Use this guide when you need reproducible evidence about CPU, RAM, process I/O, or method-level
behavior. It is an opt-in workflow: normal generation does not import or run a profiler.

## Prerequisites

- CPython 3.14.6 through uv.
- Profiling tools installed with `uv run just performance-tools-install`.
- A deterministic fixture for gated checks, or explicit local ELF/index/dump paths for environmental
  evidence. Proprietary inputs and raw profiles stay outside Git.

Check the current environment first:

```powershell
uv run ddon-dwarf-reconstructor performance doctor
```

## Deterministic fixture

Run the budgeted fixture without real assets:

```powershell
uv run just test-performance-fixtures
uv run ddon-dwarf-reconstructor performance benchmark --iterations 1
```

The runner records wall time, CPU user/system time, peak RSS/VMS, process read/write counters,
sample count, bounded stdout/stderr, and an atomic manifest. `benchmark` additionally uses pyperf
for repeated command values and stores its JSON result as an external artifact.

## Warm real-asset profile

Use the explicit indexed path and record warm state. The command below profiles the current
`export-knowledge` tree; it does not use the retired legacy CLI shape:

```powershell
uv run ddon-dwarf-reconstructor performance profile resources/DDOORBIS.elf `
  --symbol rLayout `
  --dwarf-index resources/.cache/DDOORBIS.elf.llvmdwarfdump.index.sqlite3 `
  --build-id ps4-02020005 `
  --state warm `
  --profiler scalene `
  --profiler cprofile `
  --profiler pyinstrument `
  --profiler tracemalloc
```

Add `--orbis-objdump` only when its explicit local executable is part of the evidence. Add
`--profiler py-spy` for an external/native-frame cross-check; Windows permissions may record it as
partial. Raw profiles and samples are written under the OS-local performance artifact directory.

## Runtime comparison

To compare the normal interpreter with the optional Nuitka launcher and free-threaded CPython,
follow the [runtime comparison how-to](compare-runtimes.md). Runtime identity is part of the
workload fingerprint and history comparison key. The free-threaded environment must be a separate
project venv; the bare uv-managed interpreter does not contain the project package.

The current result is report-only: Nuitka's onefile launcher is slower for warm `rLayout` despite
lower peak RSS, and free-threaded CPython is slower with higher peak RSS. Exact values and
compiler/tool blockers are retained in the feature evidence and benchmark ledger.

## Cold index evidence

Run compressed-dump index construction separately through `profile-index` and use `--state cold`.
This invokes the canonical `artifacts rebuild-dump-index` command through the shared runner, with an
explicit, longer timeout and a distinct `--name`; do not compare it to the warm export:

```powershell
uv run ddon-dwarf-reconstructor performance profile-index `
  D:/research/DDON-binaries/IDA9.3/PS4_DDON_02020005_2016_12_21/DDOORBIS.elf.llvmdwarfdump.zst `
  --index-path D:/ddon-perf-artifacts/cold-dump-index.sqlite3 `
  --state cold --name cold-dump-index --timeout-seconds 3600 --profiler process-sampler
```

The compressed dump is a large environmental prerequisite. A skipped or unavailable run remains
unavailable evidence and does not replace the deterministic fixture. Request `--profiler scalene`
separately when line-level attribution of the index build is worth its additional cost.

## History and static publication

Store summaries in the tracked SQLite ledger and export the static site artifacts:

```powershell
uv run ddon-dwarf-reconstructor performance history compare --workload reconstructor
uv run just performance-history
```

The comparison key prevents mixing cold/warm state, source identity, interpreter, machine, config,
or profiler modes. Real-asset results are report-only. Fixture budgets are explicit checked-in
thresholds and are never learned from noisy history.

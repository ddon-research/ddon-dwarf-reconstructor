# Profile the application

Use this guide when you need reproducible evidence about CPU, RAM, process I/O, or method-level
behavior. It is an opt-in workflow: normal generation does not import or run a profiler.

## Prerequisites

- CPython 3.14.6 through uv.
- Profiling tools installed with `uv run just performance-tools-install`.
- A deterministic fixture for gated checks, or explicit local ELF/store/dump paths for environmental
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

Use the durable analytical-store manifest and record warm state. The command below profiles the
current `export-knowledge` tree; it does not use the retired legacy runtime lookup shape:

```powershell
$storeManifest = Join-Path $PWD 'output\analytical-dwarf\main\store-<source-sha16>\manifest.json'
uv run ddon-dwarf-reconstructor performance profile resources/DDOORBIS.elf `
  --symbol rLayout `
  --dwarf-store $storeManifest `
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

## Bounded analytical materializer profile

Before changing Parquet batching, writer rotation, or DWARF row conversion, profile the producer
with isolated output directories:

```powershell
uv run ddon-dwarf-reconstructor performance profile-materializer `
  resources/DDOORBIS.elf `
  --output-dir (Join-Path $env:TEMP 'ddon-analytical-dwarf\profiled-materializer') `
  --max-cus 8 --max-open-writers 16 --rotate-writers-every-cus 64 `
  --profiler cprofile --profiler scalene --profiler py-spy
```

Use a larger bounded `--max-cus` only after the small probe has published usable profiles. The
command runs each profiler against a separate direct-Zstandard Parquet target and retains the
process sampler, method/line artifacts, and child diagnostics in the normal performance ledger.
Do not query or load the partial stores. cProfile and py-spy can support a producer CPU/line
conclusion; on this Windows/CPython 3.14 setup, Scalene may provide only process/memory evidence
and must not be used to rank a hot line in that case.

## Native Python crash triage on Windows

When the materializer exits with an access violation, treat the process as a native-runtime crash,
not as an ordinary Python exception. The canonical bounded materializer profiler sets
`PYTHONFAULTHANDLER=1`, so the captured stderr includes Python and thread traceback evidence when
the handler can run. Python's [faulthandler documentation](https://docs.python.org/3/library/faulthandler.html)
also documents `-X faulthandler`; the handler is supplemental and cannot replace a Windows dump.

Windows Error Reporting currently retains Python dumps under
`C:\Users\morph\AppData\Local\CrashDumps`. Analyze them with the installed Windows Debugging
Tools and keep the output under C: Temp:

```powershell
$cdb = 'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe'
$dump = 'C:\Users\morph\AppData\Local\CrashDumps\python.exe.<pid>.dmp'
$log = Join-Path $env:TEMP 'ddon-analytical-dwarf\windows-dumps\python-<pid>-cdb.log'
New-Item -ItemType Directory -Path (Split-Path -Parent $log) -Force | Out-Null
& $cdb -z $dump -logo $log -c '.symfix; .reload; !analyze -v; lm; q'
```

Microsoft's [`!analyze -v`](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/-analyze)
and [CDB dump workflow](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/opening-a-crash-dump-file-using-cdb)
are the authoritative analysis path. A WER mini-dump can establish the exception, module, address,
and stack, but cannot prove heap corruption or the original invalid write; do not promote a partial
Parquet prefix or start another full traversal from a mini-dump alone.

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
  --index-path (Join-Path $env:TEMP 'ddon-analytical-dwarf\performance\cold-dump-index.sqlite3') `
  --state cold --name cold-dump-index --timeout-seconds 3600 --profiler process-sampler
```

The compressed dump is a large environmental prerequisite. A skipped or unavailable run remains
unavailable evidence and does not replace the deterministic fixture. Request `--profiler scalene`,
`--profiler cprofile`, or `--profiler pyinstrument` separately when function/line attribution of
the index build is worth its additional cost. The complete explicit trace sequence is:

```powershell
uv run just performance-profile-index-traces
```

This rebuilds separate source-bound sidecars so profiler overhead and output artifacts cannot be
mixed. The process-sampler run is the comparable resource baseline; cProfile is for deterministic
call attribution; Scalene is for Python/native line and memory attribution; and pyinstrument is
for sampled call stacks. Tracemalloc is an allocation-only diagnostic and is intentionally not in
the full-dump recipe because it materially changes runtime. Py-spy remains an optional Windows
cross-check and an unavailable or partial result is retained as such.

## History and static publication

Store summaries in the tracked SQLite ledger and export the static site artifacts:

```powershell
uv run ddon-dwarf-reconstructor performance history compare --workload reconstructor
uv run just performance-history
```

The comparison key prevents mixing cold/warm state, source identity, interpreter, machine, config,
or profiler modes. Real-asset results are report-only. Fixture budgets are explicit checked-in
thresholds and are never learned from noisy history.

# Profile the application

Use this guide when you need reproducible evidence about CPU, RAM, process I/O, or method-level
behavior. It is an opt-in workflow: normal generation does not import or run a profiler.

## Prerequisites

- CPython 3.14.6 through uv.
- Profiling tools installed with `uv run just performance-tools-install`.
- A deterministic fixture for gated checks, or explicit local ELF/store/dump paths for environmental
  evidence. Proprietary inputs and raw profiles stay outside Git.
- For Linux compatibility and Scalene line attribution, Docker Desktop or Docker Engine with the
  [pinned image workflow](https://github.com/ddon-research/ddon-dwarf-reconstructor/blob/main/ops/reconstructor/README.md).

Check the current environment first:

```powershell
uv run ddon-dwarf-reconstructor performance doctor
```

## Linux container smoke check

The container workflow keeps the source and inputs read-only while mounting logs, generated output,
DWARF caches, raw profiler files, and the performance history database separately:

```powershell
uv run just reconstructor-container-config
docker compose --file ops/reconstructor/compose.yaml build
docker compose --file ops/reconstructor/compose.yaml run --rm reconstructor performance doctor
docker compose --file ops/reconstructor/compose.yaml run --rm reconstructor `
  performance benchmark --iterations 1 `
  --timeout-seconds 120 `
  --artifact-dir /artifacts/profiles/fixture `
  --history-db /artifacts/history/fixture.sqlite3
```

The image reports the exact project CPython version and installs the `test`, `performance`, and
`analytical` uv groups from `uv.lock` with `uv sync --frozen`. Use `DDON_RECONSTRUCTOR_INPUT_DIR` for an explicit external
asset directory; never copy a proprietary ELF or compressed dump into the image. Full mount and
override details are in the [container operator guide](https://github.com/ddon-research/ddon-dwarf-reconstructor/blob/main/ops/reconstructor/README.md).

## Deterministic fixture

Run the budgeted fixture without real assets:

```powershell
uv run just test-performance-fixtures
uv run ddon-dwarf-reconstructor performance benchmark --iterations 1
```

The runner records wall time, CPU user/system time, peak RSS/VMS, process read/write counters,
sample count, bounded stdout/stderr, and an atomic manifest. `benchmark` additionally uses pyperf
for repeated command values and stores its JSON result as an external artifact.

## Linux profiler comparison

Run one unprofiled process-sampler baseline and then repeat the same workload as independent
Scalene, cProfile, pyinstrument, and py-spy runs. The container's default service is unprivileged;
run analytical-store profiling through the `doris` service profile, and run py-spy through the
combined `doris`/`py-spy` profile, which adds `SYS_PTRACE`:

```powershell
docker compose --file ops/reconstructor/compose.yaml --profile doris --profile py-spy run --rm reconstructor-doris-py-spy `
  performance profile /inputs/DDOORBIS.elf `
  --dwarf-store /workspace/output/analytical-dwarf/main/store-<source-sha16>/manifest.json `
  --symbol rLayout --state warm --profiler py-spy `
  --artifact-dir /artifacts/profiles/linux-py-spy `
  --history-db /artifacts/history/linux.sqlite3
```

Do not use a host PID namespace by default. If `SYS_PTRACE` is insufficient, one diagnostic run
may use an explicitly recorded `seccomp=unconfined` override; the result remains an environmental
permission observation. Scalene line evidence is actionable only when its retained JSON contains
non-wrapper reconstructor source-line attribution. Process-only, launcher-only, missing-output,
and permission-failed results remain partial, blocked, or unavailable.

For the module-wrapper path, the adapter scopes Scalene with
`--program-path /workspace/src/ddon_dwarf_reconstructor --profile-exclude scalene_target.py`.
This includes the full application package and removes the wrapper's `runpy.run_module` line while
keeping standard-library and site-package tracing disabled. `--profile-all` is not the normal
setting; use it only as an explicit matrix fallback with
`--profile-only /workspace/src/ddon_dwarf_reconstructor`. The repository's `--profiler all` is a
separate multi-profiler selector. Use `--cpu-only` for a smaller CPU-only artifact, and keep full
Scalene when memory attribution is required.

The adapter explicitly enables Scalene's experimental `--memory-leak-detector`. Current Scalene
also defaults it on. A completed run with empty per-file `leaks` maps reports no likely leaks for
that workload and records `scalene_leak_records=0`; it is not a proof about native allocations or a
longer-lived process.

To inspect whether a dependency or standard-library implementation is contributing meaningful
work, request a separate broad profile:

```powershell
uv run ddon-dwarf-reconstructor performance profile-dwarf-store <ELF> `
  --store-manifest <complete-manifest.json> `
  --output-dir $env:TEMP/ddon-analytical-dwarf/library-profile `
  --query-existing-doris --symbol rLayout --iterations 1 `
  --profiler scalene-libraries
```

`scalene-libraries` uses `--profile-all --profile-system-libraries`, excludes the wrapper, and is
not part of `--profiler all`; it is deliberately an optional, broader diagnostic view.

The container's py-spy adapter uses nonblocking 5 Hz sampling. Keep that rate and mode for CPython
3.14 Docker runs: the default 100 Hz setting can spend most of the run in the profiler itself
before a speedscope file is written. Nonblocking traces may contain sampling errors and remain
wall-clock/frame evidence rather than exact CPU attribution.

For a point-in-time snapshot of a running process, attach externally with:

```powershell
py-spy dump --pid <pid> --native --nonblocking --json
```

`dump` is useful when a process is hung or in a transient phase; `record` remains the repository's
bounded time-series cross-check. Keep cProfile in the explicit comparison set because it reports
deterministic call counts and cumulative builtin/library time that sampling does not replace.

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
conclusion; on a CPython 3.14 setup, Scalene may provide only process/memory or launcher evidence
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

For a container run, export the external ledger rather than the tracked repository ledger:

```powershell
docker compose --file ops/reconstructor/compose.yaml run --rm reconstructor `
  performance history export `
  --history-db /artifacts/history/linux.sqlite3 `
  --output-dir /artifacts/history/export `
  --markdown-path /artifacts/history/export/benchmark-history.md
```

Interpret Windows/Linux deltas as environmental diagnostics unless the source identity, workload,
cold/warm state, interpreter, image, configuration, and output contract are all explicitly matched.

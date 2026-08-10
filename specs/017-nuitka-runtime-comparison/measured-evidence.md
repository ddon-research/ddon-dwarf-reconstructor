# Measured evidence: Nuitka and runtime comparison

## Build and output fidelity

| Evidence | Result |
| --- | --- |
| `uv run just native-build` with Nuitka 4.1.3, MSVC 14.5, onefile | observed; latest rebuild completed in 178.4 s with 682 clcache hits, executable 18,307,072 B |
| Compiled executable `--help` smoke | observed; exits successfully |
| CPython/Nuitka/free-threaded output manifest comparison | observed; four files and aggregate SHA-256 `423849a07af72993d1910a4b58962d3fc47e31a303e1e435d0f177ddaf406194` match |

## Warm `rLayout` comparison

Three repetitions per runtime used the same ELF, source-bound index, symbol, command tree, and
process sampler. Build time is excluded from runtime measurements.

| Runtime | Mean wall | Mean peak RSS | Read/write observation |
| --- | ---: | ---: | --- |
| CPython 3.14.6 | 2.062 s | 1,579.9 MiB | approximately 1,435 MiB read, 1.49 MiB written |
| Nuitka 4.1.3 / CPython 3.14.6 onefile | 2.470 s | 1,539.0 MiB | onefile payload writes approximately 68.2 MiB per run; OS-cache effects reduce later read counters |
| CPython 3.14.6 free-threaded | 2.202 s | 1,937.9 MiB | approximately 1,435 MiB read, 1.59 MiB written |

For this representative warm workload, Nuitka is approximately 19.8% slower than regular
CPython while reducing peak RSS by approximately 41 MiB and adding onefile extraction I/O. The
free-threaded build is approximately 6.8% slower and uses approximately 358 MiB more peak RSS;
it does not provide a benefit for this single-process, largely I/O-bound workload.

## Free-threaded compatibility

The runtime-only free-threaded environment installed the application, psutil, pyelftools, Typer,
Rich, Structlog, dotenv, pyperf, py-spy, pyinstrument, pytest, and coverage. The full development
sync is blocked by Scalene 2.3.0's Windows native extension build (`LNK1104: cannot open
file 'python314.lib'`). pyinstrument imports but enables the GIL while loading its native
`stat_profile` extension, so it is not no-GIL evidence. A direct Nuitka 4.1.3 free-threaded
compile is blocked by C errors in `allocator.h`, `_gc_runtime_state`, `_Py_IMMORTAL_REFCNT`, and
`_PyStackRef` handling.

Three earlier free-threaded rows are retained as `partial` setup diagnostics: they used the bare
uv-managed base interpreter, which could not import the installed project. They are excluded from
the observed means; subsequent comparisons use the dedicated project venv.

These are explicit toolchain blockers, not replacement performance evidence.

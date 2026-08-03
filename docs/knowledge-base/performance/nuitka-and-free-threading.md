# Nuitka and free-threaded runtime evaluation

This research note records the current Windows 11 / CPython 3.14.6 evidence. It is not a default
deployment recommendation.

## Decision

Keep regular CPython as the development and correctness runtime. Keep Nuitka as an explicit,
MSVC-backed onefile deployment/performance tool. Do not adopt free-threaded CPython as a default
runtime and do not attempt to compile it with Nuitka until upstream no-GIL support is documented
and verified.

## Evidence

Three warm `rLayout` runs per variant used the same local ELF and source-bound index:

| Variant | Mean wall | Mean peak RSS | Result |
| --- | ---: | ---: | --- |
| CPython 3.14.6 | 2.062 s | 1,579.9 MiB | baseline |
| Nuitka 4.1.3 onefile | 2.470 s | 1,539.0 MiB | 19.8% slower; lower RSS; approximately 68 MiB payload writes |
| CPython 3.14.6 free-threaded | 2.202 s | 1,937.9 MiB | 6.8% slower; approximately 358 MiB higher RSS |

All three produced byte-identical output manifests with aggregate SHA-256
`423849a07af72993d1910a4b58962d3fc47e31a303e1e435d0f177ddaf406194`.

The comparison is stored as runtime-aware rows in
`resources/performance/benchmarks.sqlite3`; raw manifests and build reports remain under
`D:\ddon-perf-artifacts`.

## Compatibility findings

- Nuitka 4.1.3 builds regular CPython 3.14.6 with MSVC 14.5 and passes the CLI smoke test.
- The previous `TYPE_CHECKING`/forward-annotation pattern in `file_registry.py` and the
  self-referential annotation in `dwarf_config.py` required deferred annotations for Nuitka.
- Core dependencies install and run under free-threaded CPython.
- Scalene 2.3.0 is blocked on Windows `cp314t` by a native link failure for `python314.lib`.
- pyinstrument 5.1.3 imports on `cp314t`, but its native `stat_profile` extension enables the GIL;
  it is therefore not valid no-GIL profiler evidence.
- Nuitka 4.1.3 is blocked on free-threaded CPython by allocator, GC, stack-reference, and
  immortal-reference C API errors. This agrees with the current official roadmap.

See the [runtime comparison how-to](../../how-to/compare-runtimes.md), the [Nuitka package
configuration guide](https://nuitka.net/user-documentation/nuitka-package-config.html), and the
[feature evidence](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/017-nuitka-runtime-comparison).

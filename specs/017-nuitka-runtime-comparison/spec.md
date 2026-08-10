# Feature 017: Nuitka and runtime comparison

**Status:** Implemented evaluation slice; free-threaded Nuitka remains blocked by upstream
compiler/runtime incompatibility.

## Goal

Establish whether the optional Nuitka launcher improves the DDON reconstructor and whether
free-threaded CPython is a viable runtime for the application and its profiling toolchain.

## Requirements

- **RTC-001:** The canonical performance runner MUST execute the same warm real-asset workload
  under regular CPython, a validated Nuitka launcher, and an explicitly installed free-threaded
  CPython runtime.
- **RTC-002:** Runtime identity MUST include implementation, Python version, GIL state, and
  executable identity in workload manifests and historical rows.
- **RTC-003:** The comparison MUST preserve deterministic generated outputs byte-for-byte and
  report CPU, wall, RSS, and process I/O evidence separately from build time.
- **RTC-004:** Nuitka build artifacts, compiler reports, and free-threaded virtual environments
  MUST remain outside Git. The tracked ledger stores summaries and external references only.
- **RTC-005:** Dependency installation and compiler failures MUST be retained as explicit
  unavailable, partial, or blocked evidence; they MUST NOT become normal-run requirements.

## Boundary

This slice does not make Nuitka the default launcher, does not add a free-threaded CI matrix, and
does not treat the current free-threaded/Nuitka failure as an application correctness failure.
Nuitka remains an opt-in deployment/performance tool. Scalene remains a regular-CPython profiler
because its Windows native extension currently fails to build for `cp314t`; pyinstrument is not
valid no-GIL evidence because its current native `stat_profile` extension enables the GIL when
imported.

## Acceptance

The feature is accepted when the runtime-aware runner, build recipe, comparison command, tests,
tracked history, static documentation, and measured evidence all pass the root quality loop, and
the evidence distinguishes the observed CPython/Nuitka/free-threaded results from blocked
free-threaded Nuitka compilation.

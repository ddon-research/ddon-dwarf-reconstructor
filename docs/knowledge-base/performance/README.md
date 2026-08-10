# Performance evidence

This knowledge-base section records profiling tool decisions and generated benchmark history. The
current workflow is source-bound, opt-in, and explicit about deterministic versus environmental
evidence.

- [Benchmark history](benchmark-history.md)
- [Feature 018 algorithm audit](algorithm-audit.md)
- [Nuitka and free-threaded runtime evaluation](nuitka-and-free-threading.md)
- [Linux container profiling evidence](https://github.com/ddon-research/ddon-dwarf-reconstructor/blob/main/specs/016-performance-profiling/measured-evidence.md#linux-container-evidence)
- [Feature specification](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/016-performance-profiling)
- [Performance how-to](../../how-to/profile-performance.md)
- [Performance command reference](../../reference/performance.md)

Scalene is the primary sampled CPU/native/memory profiler. Use the optional
`--profiler scalene-libraries` mode when dependency or standard-library alternatives are under
consideration; keep the normal package-scoped profile as the application decision surface. The
experimental leak detector is enabled explicitly, cProfile remains a deterministic call-count
cross-check, and py-spy supports both bounded external recording and point-in-time `dump` snapshots.

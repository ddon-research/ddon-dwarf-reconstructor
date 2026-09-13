# Roadmap

Spec Kit features are the roadmap and decision record. This page is an index, not a second set of
requirements. Status is derived from each feature's `spec.md` and its task checklist; unfinished
tasks remain visible.

| Feature | Current status | Roadmap focus |
| --- | --- | --- |
| [001 Header foundation](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/001-header-foundation) | Observed-partial; 31 unchecked tasks | ABI-oriented header reconstruction and explicit MSVC/IDA/assembly evidence |
| [002 Maintainability and architecture](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/002-maintainability-architecture) | Implemented and acceptance-verified | maintainability limits and architecture policy |
| [003 DWARF specification pipeline](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/003-dwarf-specification-pipeline) | Implemented | canonical JSON/Markdown specifications and manifests |
| [004 Tooling modernization](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/004-tooling-modernization) | Implemented; 1 deferred task | typed CLI and reproducible root/nested tooling |
| [005 Tooling script retirement](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/005-tooling-script-retirement) | Implemented | one `just` source of truth and typed maintenance tooling |
| [006 Clean architecture audit](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/006-clean-architecture-audit) | Tier 1/2 complete; Tier 3 deferred | evidence-preserving boundary convergence |
| [007 Observability and diagnostics](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/007-observability-and-error-diagnostics) | Slice complete; real-asset/performance deferred | bounded structured logs and chained failures |
| [008 Testing pyramid](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/008-testing-pyramid-validation) | Completed | taxonomy-enforced validation pyramid |
| [009 DWARF 2-4 correctness](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/009-dwarf2-4-correctness-audit) | Implemented; 1 deferred task | producer facts, semantic index, real-header loop-back |
| [010 Toolchain evidence](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/010-toolchain-evidence) | Implemented; external SDK checks explicit | bounded additive external-tool evidence |
| [011 CI hardening](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/011-ci-actions-hardening) | Complete | pinned workflows and local/hosted parity |
| [012 Documentation platform](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/012-documentation-platform) | Implemented; acceptance-verified | Zensical, Diátaxis, arc42, Mermaid/UML, Pages, and graph readiness |
| [013 Documentation style and governance](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/013-documentation-style-governance) | Style contract implemented; graph work moved to `KG-001` | reusable tone, page intent, arc42 mapping, evidence labels, and authoring loop |
| [014 Architecture and developer observability docs](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/014-documentation-architecture-observability) | Implemented, merged, and publicly verified | Langfuse/SonarQube how-tos, arc42 section 8, source-backed C4/UML views, and Pages verification |
| [015 LadybugDB knowledge graph](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/015-ladybugdb-knowledge-graph) | Draft; LadybugDB-first evaluation gate | versioned JSONL loader, import fidelity, deterministic queries, provenance, and operational evidence |
| [016 Performance profiling](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/016-performance-profiling) | Implemented; fixture and explicit real-asset evidence recorded | source-bound CPU/RAM/I/O/method evidence, SQLite history, and static exports |
| [017 Nuitka and runtime comparison](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/017-nuitka-runtime-comparison) | Evaluation slice implemented; free-threaded Nuitka blocked upstream | runtime-aware CPython/Nuitka/free-threaded comparison and compiler/dependency evidence |
| [018 Performance and algorithm audit](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/018-performance-algorithm-audit) | Complete; implementation, evidence, and repository gates pass | source-bound warm/cold traces, candidate decisions, and deterministic optimization evidence |
| [019 Analytical DWARF store](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/019-analytical-dwarf-store) | Doris serving promoted; file-backed replacement, Flight SQL, and semantic validation partial/unresolved | one-pass lossless materialization, native serving evidence, query parity, and explicit replacement gates |
| [020 Documentation API reference](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/020-documentation-api-reference) | Implemented; 305 modules and local repository gates verified | exhaustive source-derived Python module reference with deterministic generation and fail-closed docs validation |
| [021 C++ reconstruction architecture](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/021-cpp-reconstruction-architecture) | In progress; characterized slices and deterministic gates verified, real-asset acceptance blocked | repository-wide source review, fresh all-output baselines, characterized reconstruction/toolchain boundaries, and exact parity with a 110% runtime limit |

## Next best step

The current tranche is evidence-led convergence. Feature 001 is the real-asset implementation
record: header publication and host MSVC closure are observed, while ABI, instruction effects,
NIDs, static parity, and live behavior remain independent gates. Feature 019 is the serving and
validator record: Doris is the normal analytical runtime, while file-backed replacement, Flight
SQL, and semantic validation remain partial or unresolved. Feature 021 now owns the characterized
C++ reconstruction boundaries, CU-qualified method context, output comparator, and deterministic
workflow provenance check. Its next implementation work is review-coverage closure and the
source-bound T010/T011/T022/T060 preflight once the recorded Doris BE blocker is resolved.
`KG-001` remains deferred and is owned only by Feature 015; Features 013 and 014 retain pointers
to that record.

## Status discipline

Mark a task complete only with a file, test, command output, or retained artifact. Keep blocked
external prerequisites in the feature artifact and label them as deferred; do not convert them
into green default evidence.

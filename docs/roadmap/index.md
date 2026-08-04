# Roadmap

Spec Kit features are the roadmap and decision record. This page is an index, not a second set of
requirements. Status is derived from each feature's `spec.md` and its task checklist; unfinished
tasks remain visible.

| Feature | Current status | Roadmap focus |
| --- | --- | --- |
| [001 Header foundation](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/001-header-foundation) | Draft; 29 unchecked tasks | ABI-oriented header reconstruction and explicit MSVC/IDA evidence |
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
| [018 Performance and algorithm audit](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/018-performance-algorithm-audit) | Evidence and implementation slice complete; repository gates pending | source-bound warm/cold traces, candidate decisions, and deterministic optimization evidence |

## Next best step

The documentation architecture refinement, feature 016 profiling evidence, feature 017 runtime
evaluation, and the Feature 018 audit are published as evidence slices; Feature 018's repository
gates remain visible in its task list. The next technical integration is the LadybugDB-first
`KG-001` evaluation: define a
versioned loader over the existing JSONL bundle, verify import fidelity, and add deterministic
query fixtures. Complete the deferred real-asset/compiler evidence in features
001, 004, 007, and 009 as separate evidence slices. Do not publish a graph
projection until its schema, provenance, authority, and acceptance evidence are defined.

## Status discipline

Mark a task complete only with a file, test, command output, or retained artifact. Keep blocked
external prerequisites in the feature artifact and label them as deferred; do not convert them
into green default evidence.

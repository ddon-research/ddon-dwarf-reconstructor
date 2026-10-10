# Roadmap

This frozen index records the Python project's implementation state at retirement. Spec Kit
features preserve the requirements and historical decisions; their unchecked tasks remain
unfinished. Development has moved to an unpublished Rust rewrite, and this repository has no
active implementation queue. See the [archive status](../reference/project-status.md).

| Feature | Current status | Roadmap focus |
| --- | --- | --- |
| [001 Header foundation](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/001-header-foundation) | Retired with incomplete acceptance; unchecked tasks preserved | ABI-oriented header reconstruction and explicit MSVC/IDA/assembly evidence |
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
| [019 Analytical DWARF store](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/019-analytical-dwarf-store) | Retired with incomplete acceptance; Doris serving evidence retained | one-pass materialization and native serving; replacement and semantic validation remain partial/unresolved |
| [020 Documentation API reference](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/020-documentation-api-reference) | Implemented; final inventory contains 388 modules | exhaustive source-derived Python module reference with deterministic generation and fail-closed docs validation |
| [021 C++ reconstruction architecture](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/021-cpp-reconstruction-architecture) | Retired with incomplete acceptance | repository-wide review, full-corpus parity, and matching workload performance obligations remain open |
| [022 C++ compilation repair](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/022-cpp-compilation-repair) | Retired with incomplete acceptance | partial declaration repair; all-289-root compilation and semantic acceptance remain open |
| [023 C++ declaration IR](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/023-cpp-declaration-ir) | Retired with incomplete acceptance; specified but unimplemented | preserved design for incremental declarations and optional compiler observations |

## Unfinished work at retirement

Feature 001 retains historical header and assembly observations; PS4 ABI, instruction effects,
NIDs, static parity, and live behavior remain independent open gates. Feature 019 retains Doris
serving evidence and unresolved replacement/semantic validation work. Features 021 and 022 were
not accepted across the complete corpus. The last retained `rGrass` compiler probe passed 60/65
standalone headers and failed aggregate compilation; later method-template changes in the final
snapshot have no fresh full-corpus compiler acceptance. Feature 023 and `KG-001` remain designs,
not completed implementations. None of these records establishes the Rust rewrite's behavior.

## Status discipline

Mark a task complete only with a file, test, command output, or retained artifact. Keep blocked
external prerequisites in the feature artifact and label them as deferred; do not convert them
into green default evidence.

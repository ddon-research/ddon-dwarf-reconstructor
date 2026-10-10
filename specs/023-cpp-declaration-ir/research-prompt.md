# Research prompt: DWARF to faithful C++ declarations

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

Use this bounded prompt after Feature 022 repair or a source-bound blocker handoff. Its audience
is a researcher evaluating compiler integration. Deliver a decision record and reproducible small
experiments, not a speculative library list or replacement implementation.

## Context and Question

We reconstruct deterministic C++ headers from PS4 DWARF observations through a Python domain
model and Doris-backed source-bound queries. Existing `TypeReference` and `TypeScope` retain
declarators and lexical ancestry. Remaining risks concern exact identity, nested declaration
availability, aliases, enum facts, template signatures, and lawful publication ordering.

Which compiler integration best validates a project-owned declaration IR while preserving DWARF
provenance, bounded runtime, Windows operability, and explicit uncertainty? Can any alternative
solve a demonstrated residual case more faithfully than the repaired pipeline?

## Candidates and Primary Sources

Compare a pinned Clang subprocess, libclang, and LibTooling on identical fixtures. Study LLDB's
`DWARFASTParserClang` and `TypeSystemClang` for lazy completion and scope ownership; do not assume
their private debugger APIs are supported header-export interfaces. Start with the primary
sources in [research](research.md), checking versions and licenses at evaluation time.

Explain why LLVM IR lowering/Rellic does or does not retain the source concepts needed here.
Assess syntax parsers only for clearly bounded auxiliary tasks. Reuse current graph machinery
unless a measured gap justifies a dependency. No library is selected in advance beyond the
initial subprocess experiment.

## Common Experiment Corpus

1. Nested owner/member declarations, including legal out-of-class definitions and illegal shells.
2. Alias chains to incomplete types, multiple aliases to anonymous enums/aggregates, cycles.
3. Namespaced template primaries, type/non-type/template arguments, and same-spelled nested types.
4. The explicit-specialization/nested-argument counterexample from Feature 022, plus any actual
   source-bound blocker supplied by its handoff. Keep hypothetical and observed cases separate.
5. Member pointers, arrays of callables, multidimensional arrays, cv/ref-qualified methods,
   conflicting exception specifications, enum scopedness/base uncertainty, and zero-width bitfields.
6. Incomplete/conflicting DWARF, duplicate observations, offset zero, and preserved unknown forms.

Use small redistributable synthetic C++ sources. Generate temporary objects and DWARF externally,
then compare original compiler semantics with reconstructed declarations. Do not upload game
inputs, SDKs, dumps, credentials, or generated proprietary headers to external services.

## Required Output

- A candidate matrix: supported semantic facts, unsupported cases, synthesized information,
  provenance joins, API/schema stability, license, Windows packaging, pinning and maintenance cost.
- Exact source fixture hashes, tool executable/version/hash, flags/target/include environment,
  commands, outputs, and failure reproductions, stored outside source control where appropriate.
- CPU time, peak RSS, output sizes and timeout behavior for bounded cases; normal generation
  remains compiler-independent. Do not extrapolate small-fixture timings to the full corpus.
- A proposed normalized schema and evidence joining method that excludes raw AST pointer IDs.
- An adoption decision: stay with subprocess, add a native helper, or defer. A native helper needs
  a reproduced subprocess limitation and demonstrated improvement on the same case.
- Explicit unknowns and a next experiment for each unresolved fact. Unsupported evidence must
  not become guessed generic bodies, renamed types, erased fields, or invented outer definitions.

Record results in `measured-evidence.md` and update `research.md`/the compiler contract together.
Research completion is separate from passing migration, full-corpus, ABI, and performance gates.

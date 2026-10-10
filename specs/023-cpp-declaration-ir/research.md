# Research: Declaration IR and compiler integration

This decision record serves maintainers choosing the architecture after repair. It records an
initial recommendation; dependency adoption and full tool benchmarks remain unobserved.

## Decisions and Alternatives

| Candidate | Decision and rationale | Evidence required to change the decision |
| --- | --- | --- |
| Project-owned C++ declaration IR | Adopt incrementally around existing `TypeReference`/`TypeScope`; preserves source identity above output spelling | Demonstrate a simpler model meeting the same identity, provenance, and scheduling contracts |
| Clang subprocess | Initial optional validator; isolates native versioning and provides syntax/AST observations | Common fixtures expose an essential semantic query unavailable within bounded extraction |
| libclang | Evaluate, not adopted; stable C interface exposes a deliberately limited AST surface | Reproduce needed template/type information, Windows packaging, and version compatibility |
| LibTooling | Conditional native helper for richer AST access; greater version/build coupling | Reproduced subprocess gap plus pinned build, license, cost, and maintenance decision |
| LLDB DWARF-to-Clang implementation | Study lazy completion, declaration contexts, and conflict handling | An embedding proposal must prove provenance preservation and required declaration export |
| LLVM IR / Rellic | Defer; lowered representation does not retain the source declaration structure needed here | A separate function-body/decompilation requirement and fidelity contract |
| cxxheaderparser / tree-sitter | Optional syntax research only; neither establishes full C++ semantic validity | A bounded parsing task adding value without replacing compiler or DWARF authority |
| New graph library | Not selected; existing graph algorithms suffice | Measured capability/maintenance benefit beyond current SCC/order routines |

## Authority and Sources

Feature 022 now uses a local, detached clone of
[`lefticus/cppstdmd` `n4950`](https://github.com/lefticus/cppstdmd/tree/main/n4950) at
`1ef40e3d656c6e77e07ead58308e76b7b55ebf4a` for fast clause lookup. Its
[compiler-feedback rulebook](../022-cpp-compilation-repair/compiler-feedback.md) ties clauses to
reduced MSVC/Clang canaries and source-bound owner witnesses. The converted draft is a research
reference, not evidence that the historical PS4 producer used C++23. This tooling narrows
Feature 023's research questions but does not implement its declaration IR or close T001.

[Clang's tooling guide](https://clang.llvm.org/docs/Tooling.html) distinguishes the stable but
limited libclang interface from richer C++ tooling. That tradeoff supports starting at a process
boundary, then measuring whether a native helper is needed. It does not promise stable raw AST
JSON across compiler versions; normalized records belong to this project.

LLDB already tackles DWARF-to-Clang type reconstruction. Inspect
[DWARFASTParserClang](https://lldb.llvm.org/cpp_reference/DWARFASTParserClang_8cpp_source.html)
and [TypeSystemClang](https://lldb.llvm.org/cpp_reference/classlldb__private_1_1TypeSystemClang.html)
for deferred completion and context ownership. This is a design reference, not evidence of a
supported standalone header exporter or a lossless round trip for this project's Sony evidence.

[LLVM's language reference](https://llvm.org/docs/LangRef.html) describes a lower-level program
IR. [Rellic](https://github.com/lifting-bits/rellic) translates LLVM bitcode toward C; neither is
a direct solution to C++ alias visibility, lexical ownership, and declaration ordering. Preserve
those semantics in a declaration IR before considering lower-level analysis.

[cxxheaderparser](https://github.com/robotpy/cxxheaderparser) and
[tree-sitter](https://tree-sitter.github.io/tree-sitter/) can inform syntax tooling. Their parsing
results must not be mistaken for template instantiation, name lookup, ABI, or source provenance.

## Research Boundary

The review observed Clang 22.1.8 at `C:/msys64/clang64/bin/clang++.exe`, targeting
`x86_64-w64-windows-gnu`, and ran small C++17 syntax canaries. That availability is not a promoted
project profile, benchmark, or PS4 validation result. Reprobe executables and licenses before
adoption; record hashes, version, flags, includes, target/data model, and resource costs.

The [research prompt](research-prompt.md) defines a reproducible comparison. Select a tool only
after that comparison; no additional runtime dependency is part of this documentation change.

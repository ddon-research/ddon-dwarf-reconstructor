# Contract: Optional compiler validation

This proposed interface serves application orchestrators and compiler adapters. It is validation
infrastructure; ordinary generation must not invoke it implicitly or require a compiler install.

## Request

A request supplies a published bundle manifest and hashes, emission ledger, selected declaration
IDs/translation units, compiler profile, requested checks, timeout, and output/resource limits.
The adapter verifies containment and hashes before execution. Commands use argument arrays and
explicit working directories; include paths and flags belong to the profile, not ambient guesses.

The initial profile is a pinned Clang subprocess with syntax checking and bounded AST extraction.
The existing MSVC validator remains independently required. Inspect local help/version and prove
the chosen AST options on synthetic fixtures before promoting them into the profile. Profile
creation records installation source/license and executable/version/hash; no unpinned `latest`.

## Response

Return a typed result defined in [data model](../data-model.md), including complete requested-ID
coverage, normalized observations, process status, diagnostics, unsupported fields, input/raw-output
hashes, timings, peak RSS where measured, and adapter/schema versions. No result may report
`passed` after timeout, missing IDs, truncated output, unsupported schema, or failed joins.

Diagnostics preserve severity, compiler code where present, message, location, and joined
declaration IDs. Ambiguous locations retain candidates/status rather than selecting the first
matching simple name. Compiler-synthesized nodes are labeled and do not become DWARF facts.

## Normalization and Resource Boundaries

Normalize only tested fields. Do not expose native AST pointers or transient IDs as public data.
Retain aliases as declarations while also comparing canonical target types. Preserve nested
contexts and template primary/specialization relationships, including unsupported observations.

Use small selected translation units or demonstrated filtering to bound extraction. Spool large
raw output to external artifacts and enforce limits; do not load a full game AST JSON into RAM.
When a limit prevents complete extraction, return `incomplete` with a retry strategy. Cache only
under input, profile, schema, adapter, and configuration fingerprints; publish results atomically.

## Authority and Adoption

Host syntax, host canonical types, target layout, and source provenance are independent evidence
dimensions. A target triple without matching ABI/headers/toolchain support is not target proof.
libclang/LibTooling adoption requires the [research gate](../research-prompt.md), a demonstrated
subprocess limitation, and updated dependency/profile contracts. No native dependency is required
by this initial interface.

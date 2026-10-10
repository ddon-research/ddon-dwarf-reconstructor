# Validate an incremental declaration-IR slice

This guide serves implementers after Feature 022 repair or its documented blocker handoff.
It requires the locked development environment and explicit compiler profiles for optional
compiler tests. The IR and adapter paths in [tasks](tasks.md) are proposed, not available commands.

## Establish the Comparison

Follow [Feature 022's guide](../022-cpp-compilation-repair/quickstart.md) to identify the repaired
producer, source/store, roots, modes, and acceptance limits. Execute the [research prompt](research-prompt.md)
on small synthetic fixtures. Record tool availability separately from successful AST extraction.

Probe the reviewed local candidate only if it still exists:

```powershell
& 'C:/msys64/clang64/bin/clang++.exe' --version
```

This path was observed during review; it is not a portable installation guarantee or a promoted
PS4 profile. Pin the selected tool and AST extraction options through T002 before using them.

## Validate Each Migration

Run the focused tests named in the task after their modules exist, then:

```powershell
uv run just test-unit
uv run just check
uv run just test
```

For each migrated family, compare unchanged bytes and normalized semantic declarations, test
unknown/conflicting evidence, and remove superseded policy only after parity is demonstrated.
Use the emission ledger to join diagnostics; simple-name matching is not an identity check.

Compiler integration tests must include unavailable tools, nonzero exit, timeout, truncated AST,
unsupported schema, source-join ambiguity, and target mismatch. These cases must never report a
successful complete observation. Run compiler-free generation to prove runtime independence.

## Differential and Full Acceptance

Compile small redistributable fixtures to temporary objects/DWARF outside Git, reconstruct them,
and compare representable canonical types, aliases, template relationships, and lexical owners.
Do not require unavailable original macros or comments to survive. Record compiler-generated
facts separately from source observations.

After deterministic slices pass, execute Feature 022's complete real-asset/mode/determinism matrix
and retain separate MSVC, Clang, semantic, target-layout, and performance results. Measure compiler
validation overhead independently of normal generation. Finish with `uv run just coverage-ci`
and `uv run just audit`; update this guide with the implemented optional-validation invocation
only after its CLI contract has been chosen and verified. No fictional CLI is supplied here.

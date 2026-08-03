# Goal-oriented DWARF research workflow

This repository uses Codex goals for long-running investigations whose finish line is clear but
whose implementation path may change as evidence arrives. A goal is scoped to the current Codex
thread; it does not replace `AGENTS.md`, the active Spec Kit feature, or durable project policy.

The official Codex guidance is [Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex).
The useful project shape is:

```text
/goal Bring the DDON DWARF parser to an evidence-backed DWARF2-4 correctness baseline,
verified by all-CU ELF and LLVM-dump producer evidence, semantic-specification checks,
focused regressions, and the required validation gates, while preserving deterministic
provenance, offsets, cache identity, output bytes, and bounded memory. Use only the
checkout, explicit local assets, generated specification artifacts, and documented tool
surfaces. Between iterations, inspect evidence, make one cohesive refactoring slice, and
run the smallest relevant tests plus `uv run just check`. If blocked, report the exact
missing prerequisite and the action that would unlock it.
```

## Iteration stages

1. Establish the evidence surface: inspect the worktree, identify immutable inputs, and run
   `artifacts inspect-elf` and `artifacts inspect-dwarf-dump` when explicit local paths are present.
2. Build or validate the specification index with
   `uv run --project tools/dwarf_spec_pipeline dwarf-spec-pipeline audit --output-dir
   docs/knowledge-base/dwarf-specification/generated --source-root src`.
3. Convert each suspected relationship into a focused test or a documented, intentionally deferred
   contract. Preserve producer facts; derived checks must not overwrite them.
4. Refactor one owning module or adapter slice. Keep domain policy independent of pyelftools,
   SQLite, zstd, and CLI composition details.
5. Run the focused tests, `uv run just test-unit`, and `uv run just check`; then run the required
   `uv run just test` loop before moving to another slice.
6. At handoff, run coverage/audit gates and record external real-asset or MSVC validation separately.

## Completion record

Every goal handoff should separate:

- confirmed facts, with the command or artifact that proves each one;
- approximate or producer-specific behavior that is intentionally bounded;
- blocked checks and their exact missing prerequisite;
- remaining uncertainty, especially where original C++ behavior cannot be recovered from DWARF.

Budgets, elapsed time, or an incomplete implementation are not completion evidence. The goal is
complete only after the named verification surface passes or an explicit external prerequisite is
recorded as blocked for follow-up.

# Archive status and final validation

This reference serves readers reproducing the retired Python project or evaluating its evidence.
It records the frozen source, known limitations, and preservation boundary as of October 10, 2026.
This Python implementation is archived. Development has moved to an unpublished Rust rewrite.

## Preserved implementation

The implementation snapshot is commit `f0cb1af34f729ba7abfb7019bf7a4303c8a20bec`.
It preserves the 175 staged source, test, specification, and operations changes as they stood.
The retirement changes update documentation and its publication configuration; they do not repair
the Python implementation or change its acceptance criteria.

The [frozen roadmap](../roadmap/index.md) and unchecked Spec Kit tasks describe unfinished work.
Features 021 and 022 are retired with incomplete acceptance. Feature 023 remains specified and
unimplemented. The additional `specs/017-dwarf-fidelity-and-clean-cpp/` notes describe research for
the Rust successor; they are separate from Python Feature 017's Nuitka evaluation and do not
establish accepted behavior in either implementation.

## Compiler and evidence limits

The last retained source-bound `rGrass` v15 report attempted 65 headers: 60 passed, five failed,
none timed out, and aggregate MSVC compilation failed. Its manifest hash is
`b4d2ff4d0c18f90425cdbf1dfc916790a4879f642b511ccece9c9d3454263340`; the compiler
report hash is `c9ccf4ae48d5427a706b8c082baf4fe6c798e6c57ac1a3c6f999946dd41f1adf`.
The retained report is under
`output/compilation-repair-022/t011-20260926/real-rGrass-nested-primary-v15-validation/`.

That report precedes the final method-template changes. It does not validate the final snapshot,
all 289 Season 2 roots, semantic completeness, PS4 ABI/layout, or matching workload performance.
Reduced Clang/MSVC canaries and diagnostic copies remain bounded experiments. Historical passing
quality reports describe their original slices, not the retirement snapshot.

## Retirement checks

The locked contract uses CPython 3.14.7 and uv 0.12.3. On the retirement workstation uv 0.13.0
was installed globally; an isolated pinned tool runs the historical recipes without changing it:

```powershell
uvx --from uv==0.12.3 uv run --locked just docs-check
```

The following recipe results were observed on the retirement workstation. Failures remain part
of the frozen implementation; retirement does not turn them into passing acceptance.

| Recipe | Retirement result |
| --- | --- |
| `docs-check` | Passed: 388 API modules, 17 Mermaid diagrams, and strict site build |
| `test-unit` | Failed: 1,465 passed, one failed, seven deselected |
| `check` | Failed at existing `class_parser_methods.py` formatting; independent structure check also fails at projection complexity 11 against limit 10 |
| `test` | Failed: 782 passed, one failed, 12 deselected; stopped at the first failure |
| `coverage-ci` | Failed at the same test after 782 passes; the complete coverage gates were not reached |
| `audit` | Passed: zero messages |

The unit/default/coverage failure is
`test_transport_caches_unavailable_fe_profile_endpoint`: the local configuration also attempts
`doriscli`, while the assertion expects only the cached FE HTTP attempt. This is an observed
failure, not evidence of an unavailable serving database.

## Preservation and publication

The external backup is
`D:/research/archives/ddon-dwarf-reconstructor/20261010-160250/`. It contains Git bundles,
ref inventories, snapshot identities, documentation review inventory, and validation logs.
The implementation bundle passed mirror restoration and Git integrity verification before
branch cleanup. A final bundle records the retirement documentation as well.

Existing history and tags are retained. Only branches fully contained in final `main` are eligible
for deletion; unmerged branches and Dependabot PRs remain preserved. Scratch investigations,
the local DWARF index, durable Parquet stores, Docker volumes, caches, generated output, and
credentials remain local and are not added to the source snapshot. A Git bundle does not contain
untracked or ignored files; their local preservation is a separate obligation.

The final documentation site is published before GitHub archival. Repository archival is the last
operation and makes GitHub's repository surfaces read-only; it does not establish runtime or
compiler correctness. [GitHub archival documentation](https://docs.github.com/en/repositories/archiving-a-github-repository/archiving-repositories)

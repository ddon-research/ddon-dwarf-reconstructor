# Testing pyramid and validation loop

## Context

The repository has a large and valuable unit suite because DWARF parsing and header rendering have
many pure decision points. That suite alone cannot prove that source identity, application
orchestration, serialization, atomic publication, and user-visible distribution behavior still
work together. Real ELF checks are also expensive and depend on local proprietary inputs.

The pre-audit root baseline exposed 429 collected tests: 407 unit, 2 integration, 1 performance,
1 packaging, and 18 without a useful scope/purpose marker. The
knowledge exporter integration module was marked unit even though it exercises real temporary-file
publication and evidence serialization. The nested DWARF specification project had 15 collected
tests with scope markers but no purpose markers.

## Durable policy

The root suite has three mutually exclusive scopes:

- `unit` for isolated decisions and controlled boundaries;
- `integration` for multiple real project components with deterministic local fixtures;
- `acceptance` for user-visible CLI, distribution, or external-artifact flows.

Purpose markers are orthogonal:

- `functional` for behavior/output correctness;
- `regression` for a stable contract or previously observed defect;
- `non_functional` for performance, quality, maintainability, resource, and operational behavior.

`performance`, `slow`, `real_asset`, `packaging`, and `quality` are qualifiers, not substitutes for
scope or purpose. Collection fails for missing/ambiguous scope, missing purpose, performance or
quality tests without `non_functional`, real-asset tests outside integration/acceptance, and
packaging tests outside acceptance.

The default correctness loop includes deterministic integrations. The real exporter path is now
required integration/regression evidence; it uses temporary source/output files, actual source
identity hashing, model serialization, manifest publication, and Orbis/DWARF evidence objects.
The real PS4 generator and warm budget remain explicit `real_asset` acceptance/performance checks.
This keeps the quality loop meaningful on machines and CI workers without the 800 MB ELF or the
30+ GB expanded dump.

The required correctness tier also carries cross-platform filesystem evidence. The source identity
catalog must reuse an unchanged object after relocation on POSIX and Windows, while still rehashing
ctime-only mutation at an existing path. A local Windows pass is therefore insufficient by itself;
the Ubuntu Actions job is part of the contract.

## Validation evidence

After the DWARF2-DWARF4 audit and Sonar setup update, collection reports 443 tests with zero unscoped and zero
no-purpose items. The required correctness selection contains 439 tests; the remaining tests are
one performance benchmark, one packaging acceptance, and two real-asset acceptance tests beyond
the benchmark. The fast unit tier passes 437 tests, and the deterministic exporter integration
tier contains two tests. The nested specification project contains 18 tests: 15 unit, 2
integration, and 1 official artifact test.

The evidence loop also has explicit read-only commands:

```text
uv run ddon-dwarf-reconstructor artifacts inspect-elf <absolute-ELF-path>
uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-dump <absolute-dump-path>
uv run --project tools/dwarf_spec_pipeline dwarf-spec-pipeline audit \
  --output-dir docs/knowledge-base/dwarf-specification/generated --source-root src
uv run --project tools/dwarf_spec_pipeline dwarf-spec-pipeline validate \
  --output-dir docs/knowledge-base/dwarf-specification/generated
```

The ELF pass is an all-CU header/top-level-attribute scan; the compressed-dump pass is a bounded
streaming counter pass over the expanded text representation. Neither replaces the parser’s
relationship tests or the explicit external compiler/Orbis acceptance loop.

The executable contract lives in:

- `tests/support/quality/taxonomy.py` and `tests/conftest.py`;
- `pyproject.toml` and the root `justfile`;
- `specs/008-testing-pyramid-validation/contracts/testing-policy.md`.

## References

- [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
- [pytest custom markers](https://docs.pytest.org/en/stable/example/markers.html)
- [pytest invocation](https://docs.pytest.org/en/stable/how-to/usage.html)
- [Hypothesis quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html)
- [Tagging PyTest Tests](https://www.tdda.info/tagging-pytest-tests)
- [Testing Your Code](https://docs.python-guide.org/writing/tests/)
- [Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)

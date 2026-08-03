# Test suite guide

The root test suite is pytest-only. Use the repository's locked environment and `just` recipes:

```text
uv run just test-unit
uv run just test-integration
uv run just test
uv run just test-without-integration  # exceptional iteration shortcut
uv run just coverage-ci
uv run just audit
```

See the [testing and evidence reference](../docs/reference/testing.md) for the full marker
contract, pyramid rationale, real-asset policy, and nested specification-project loop.

## Ownership

- `tests/application/`, `tests/config/`, `tests/domain/`, and `tests/infrastructure/` mirror the
  production boundaries.
- `tests/performance/` contains explicit non-functional budgets.

The deterministic fixture performance budget uses the reusable process runner. Run it with
`uv run just test-performance-fixtures`; use `uv run just test-performance-real-assets` only when
the named local PS4 paths are configured. Resource and profiler artifacts are written outside the
checkout, while summaries are recorded through the performance history workflow.
- `tests/packaging/` contains isolated distribution acceptance.
- `tests/quality/` contains architecture, maintainability, manifest, coverage, and taxonomy gates.
- `tests/support/` contains typed DIE builders, regression manifest helpers, and test-policy code.

## Marker rule

Every collected root test has exactly one scope: `unit`, `integration`, or `acceptance`. Every test
has a purpose: `functional`, `regression`, or `non_functional`. Performance, quality, packaging,
slow, and real-asset qualifiers are explicit and validated during collection by
`tests/conftest.py`.

The normal `test` and coverage recipes include deterministic integration tests. Use
`test-without-integration` only to shorten an iteration while diagnosing a local change; run the
required loop before handoff.

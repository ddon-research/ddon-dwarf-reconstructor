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

See [docs/TESTING.md](../docs/TESTING.md) for the full marker contract, pyramid rationale, real
asset policy, and nested specification-project loop.

## Ownership

- `tests/application/`, `tests/config/`, `tests/domain/`, and `tests/infrastructure/` mirror the
  production boundaries.
- `tests/performance/` contains explicit non-functional budgets.
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

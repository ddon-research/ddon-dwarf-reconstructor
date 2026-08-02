# Testing Policy Contract

## Marker contract

Each collected test must have exactly one scope marker:

| Scope | Meaning | Default selection |
| --- | --- | --- |
| `unit` | Isolated domain/application/adapter logic with controlled boundaries | `test-unit`, `test` |
| `integration` | Multiple real project components with deterministic local fixtures | `test-integration`, `test` |
| `acceptance` | User-visible CLI, installed distribution, or external artifact flow | explicit acceptance recipes |

Each test must have at least one purpose marker:

| Purpose | Meaning |
| --- | --- |
| `functional` | Product behavior or output correctness |
| `regression` | A stable contract or previously observed failure |
| `non_functional` | Performance, quality, maintainability, resource, or operational behavior |

Qualifiers:

| Marker | Meaning |
| --- | --- |
| `performance` | Measures a time/throughput/resource budget; must also be `non_functional` |
| `slow` | Expected to exceed the normal fast feedback budget |
| `real_asset` | Requires an explicit local ELF, dump, compiler, or generated external artifact |
| `packaging` | Installs or exercises the built distribution in an isolated environment |
| `quality` | Tests the repository's architecture, structure, coverage, or tooling policy |

## Required command contract

```text
uv run just test-unit
uv run just test-integration
uv run just test
uv run just test-without-integration  # exceptional opt-out
uv run just coverage-ci
uv run just audit
uv run just test-performance           # explicit local asset/budget tier
uv run just package-smoke              # explicit isolated distribution tier
```

`test` is the default correctness loop. It includes deterministic integration tests and excludes
only explicit environmental/non-required qualifiers (`performance`, `packaging`, `real_asset`).
`test-without-integration` exists for iteration speed and is not a merge-quality substitute.

## Evidence contract

- Generated headers and knowledge bundles use exact byte/hash manifests.
- Real-asset and performance reports record input identity, producer/configuration identity, cold
  or warm state, duration, and any skipped prerequisite.
- A skipped external test is reported as unavailable evidence; it is not counted as a passing
  replacement for the deterministic integration tier.

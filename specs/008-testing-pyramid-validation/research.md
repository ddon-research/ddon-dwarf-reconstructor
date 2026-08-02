# Research: Testing Pyramid and Validation Loop

## Sources reviewed

- [Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
  defines a Goal as a persistent objective with measurable outcome, verification surface,
  constraints, boundaries, iteration policy, and a blocked stop condition.
- [pytest custom markers](https://docs.pytest.org/en/stable/example/markers.html) recommends
  centrally registered markers, `strict_markers`, and module/class markers for consistent
  selection.
- [pytest invocation](https://docs.pytest.org/en/stable/how-to/usage.html) documents marker and
  expression-based selection as part of the normal runner contract.
- [Hypothesis quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html) supports
  property-based coverage for pure parser, declarator, and type invariants; it does not replace
  integration or acceptance tests.
- [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
  recommends many small tests, fewer coarse-grained tests, and very few high-level tests, while
  keeping terminology consistent within a codebase.
- [Tagging PyTest Tests](https://www.tdda.info/tagging-pytest-tests) reinforces tagging as a way
  to select focused subsets without losing a coherent suite.
- The supplied Real Python, Python Guide, Hypothesis, and grouping references were used as
  secondary guidance for practical pytest organization and property-based testing.

## Decisions

1. Integration is required by default when it can run on deterministic local fixtures.
2. Proprietary real-asset checks are qualified as `real_asset` and remain explicit environmental
   acceptance evidence; a missing asset must not erase the required local integration signal.
3. Performance is a non-functional purpose and a dedicated qualifier, never an implicit property
   of a slow test.
4. Coverage remains a risk signal and threshold, not the definition of functional completeness.
5. The root project owns the full taxonomy hook; the nested specification project mirrors the
   vocabulary but keeps its own project boundary.

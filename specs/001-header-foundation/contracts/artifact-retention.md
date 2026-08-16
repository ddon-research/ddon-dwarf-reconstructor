# Artifact retention contract

This contract classifies generated and diagnostic artifacts without authorizing deletion of
historical evidence. It is intentionally narrow: the repository does not provide a broad
`clean-all` operation.

| Class | Paths or pattern | Policy |
| --- | --- | --- |
| Durable source-bound analytical store | `output/analytical-dwarf/main/store-<source-sha16>/` | Retain locally. Reuse only after manifest/source/producer/schema/configuration validation. Never remove through `clean-transient`. |
| Current source-derived implementation evidence | `output/ps4/implementations/` and matching external manifests | Retain until a newer source-bound publication supersedes it. Header bytes and canonical `.s`/`.o` eligibility are not cleanup targets. |
| Historical acceptance evidence | The dated 2,745-header, blocked 1,653-header, current 2,760-header, and 1,150-method records under `specs/` plus their external report paths | Retain as dated evidence. Counts must not be merged or silently reclassified. |
| External validator/benchmark evidence | `%TEMP%\ddon-*` reports, profiles, tool outputs, and crash diagnostics named by feature records | Retain when referenced by an acceptance or measured-evidence record. The contract does not purge them automatically. |
| Disposable repository transient outputs | `.pytest_cache/`, `htmlcov/`, `.coverage`, `coverage.json`, `coverage.xml`, `test-results.xml`, and `site/` | May be removed only by the explicit `just clean-transient` recipe. This list excludes `output/`, `resources/`, `logs/`, source-bound caches, and retained evidence. |
| Prohibited source-control artifacts | PS4 ELF/SELF inputs, expanded dumps, generated header bundles, Parquet/JSONL stores, SQLite sidecars, credentials, and raw SDK content | Keep outside source control and outside cleanup targets; reference only by external path and identity. |

The current worktree was not cleaned while this contract was added. Any future repair or purge
must resolve and inventory exact targets first, preserve a valid prior publication, and publish a
replacement atomically.

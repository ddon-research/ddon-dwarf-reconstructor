# Implementation plan

1. Add typed analytical records, manifests, query ports, and deterministic tagged-value encoding.
2. Add the pyelftools-backed one-pass producer with an atomic typed row sink, raw-section, and manifest publication; keep JSONL opt-in.
3. Add direct typed Parquet adapters with explicit unavailable diagnostics; retain JSONL query support for audit stores.
4. Add the Doris Compose service, native loading surface, bounded benchmark runner, and an opt-in
   Arrow Flight SQL comparison profile with explicit FE/BE preflight evidence.
5. Wire `generate` and `export-knowledge` to a source-bound store manifest; remove normal dump-index and lazy-scan lookup after parity.
6. Add fixture, integration, real-asset, performance, and acceptance evidence; synchronize docs and `just` recipes.

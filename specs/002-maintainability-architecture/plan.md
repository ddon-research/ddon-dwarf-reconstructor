# Implementation Plan: Maintainability and Architecture Hardening

## Phase 0: Baseline and contracts

- [x] Capture fixture and real PS4 header manifests before refactoring.
- [x] Add typed generation/evidence contracts without changing public façades.
- [x] Record current output, cache, coverage, and performance observations.

## Phase 1: Quality gates

- [x] Add structure and import-boundary checkers under `scripts/quality/`.
- [x] Enable Ruff McCabe checks and add focused Prospector configuration.
- [x] Add Hypothesis and regression testing support.
- [x] Add tests for the quality and manifest utilities.

## Phase 2: Domain and application decomposition

- [x] Centralize definition selection, method evidence, source identity, type
  classification, and special-header rendering.
- [x] Split class parsing, type resolution, hierarchy building, and header rendering
  behind compatibility façades.
- [x] Replace repeated generation workflows with one typed application workflow.

## Phase 3: Infrastructure and test reorganization

- [x] Split cache, index, compressed-dump, exporter, Orbis, and CLI responsibilities.
- [x] Move or re-export legacy utilities using package-relative imports.
- [x] Mirror tests to the owning package and extract typed fixture builders.

## Phase 4: Convergence

- [x] Add missing negative, ambiguity, corruption, timeout, and determinism tests.
- [x] Raise coverage and enforce size/complexity/boundary gates.
- [x] Run fixture, fresh-process, warm-cache, compiler, real-artifact, and performance
  acceptance checks.
- [x] Update architecture, testing, README, workflow, and Spec Kit documentation.

The cold sidecar rebuild was verified against the documented 1.09 GB
compressed dump in 295.6 seconds. It published the 206,422,016-byte index
atomically, and cold-index generation matched the warm-header manifest.

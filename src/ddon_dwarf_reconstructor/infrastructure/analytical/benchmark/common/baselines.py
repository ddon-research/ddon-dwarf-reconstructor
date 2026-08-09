"""Explicit baseline workloads for the analytical DWARF benchmark."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from .....domain.ports.dwarf_lookup import DwarfLookupPort
from .....domain.services.lazy_dwarf_index_service import LazyDwarfIndexService
from .....domain.services.search_result import SearchResult
from ....artifacts import SourceIdentityCatalog
from ....config import DwarfRuntimeConfig
from ....elf_session import ElfDwarfSession
from .metrics import distribution, measure


def current_runtime_baseline(
    elf: Path,
    output_dir: Path,
    symbols: tuple[str, ...],
    iterations: int,
    search_timeout: float | None = None,
) -> dict[str, Any]:
    """Measure the pre-materialization live pyelftools lookup path.

    This is intentionally an opt-in validation workload.  It opens the ELF and
    constructs the legacy lazy lookup service in each cold sample, then keeps a
    single service alive for warm samples.  It does not alter the normal
    generation command, which remains source-store-only.
    """
    effective_timeout = (
        DwarfRuntimeConfig.from_environment().search_timeout_seconds
        if search_timeout is None
        else search_timeout
    )
    if effective_timeout <= 0:
        raise ValueError("search_timeout must be positive")
    cache_root = output_dir / "current-runtime-baseline"
    cache_root.mkdir(parents=True, exist_ok=True)
    measurements = [
        _current_symbol_measurement(elf, cache_root, symbol, iterations, index, effective_timeout)
        for index, symbol in enumerate(symbols)
    ]
    return {
        "status": "observed",
        "backend": "live-pyelftools-lazy-index",
        "source_path": str(elf.resolve()),
        "search_timeout_seconds": effective_timeout,
        "queries": measurements,
    }


def _current_symbol_measurement(
    elf: Path,
    cache_root: Path,
    symbol: str,
    iterations: int,
    index: int,
    search_timeout: float,
) -> dict[str, Any]:
    cold_result, cold_metrics = measure(
        lambda: _search_in_fresh_session(
            elf, cache_root / f"cold-{index}.json", symbol, search_timeout
        )
    )
    with ElfDwarfSession(elf) as session:
        if session.dwarf_info is None:
            raise RuntimeError(f"Live baseline opened no DWARF info for {elf}")
        service = LazyDwarfIndexService(
            session.dwarf_info,
            cache_file=str(cache_root / "warm.json"),
            source_file_path=elf,
            source_identity=SourceIdentityCatalog(),
            search_timeout=search_timeout,
        )
        lookup = cast(DwarfLookupPort, service)
        warm_results = [
            measure(lambda: lookup.targeted_symbol_search(symbol, timeout=search_timeout))[1]
            for _ in range(iterations)
        ]
    return {
        "query": "find_definitions",
        "symbol": symbol,
        "status": _search_status(cold_result),
        "matches": 1 if cold_result.candidate is not None else 0,
        "cus_searched": cold_result.cus_searched,
        "cold": cold_metrics,
        "warm": distribution(warm_results),
    }


def _search_in_fresh_session(
    elf: Path, cache_file: Path, symbol: str, search_timeout: float
) -> SearchResult:
    with ElfDwarfSession(elf) as session:
        if session.dwarf_info is None:
            raise RuntimeError(f"Live baseline opened no DWARF info for {elf}")
        service = LazyDwarfIndexService(
            session.dwarf_info,
            cache_file=str(cache_file),
            source_file_path=elf,
            source_identity=SourceIdentityCatalog(),
            search_timeout=search_timeout,
        )
        return cast(DwarfLookupPort, service).targeted_symbol_search(symbol, timeout=search_timeout)


def _search_status(result: SearchResult) -> str:
    return result.status.value

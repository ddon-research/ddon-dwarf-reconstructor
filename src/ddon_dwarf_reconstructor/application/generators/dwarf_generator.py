#!/usr/bin/env python3

"""DWARF-to-C++ header generator orchestrator (Application Layer).

This is the main generator that orchestrates the modular components:
- TypeResolver: Type resolution and typedef handling
- ClassParser: DWARF class parsing
- HeaderRenderer: C++ header generation
- HierarchyBuilder: Inheritance hierarchy management
- PackingAnalyzer: Struct packing analysis
"""

from __future__ import annotations

import logging
from pathlib import Path
from time import perf_counter

from ...core.observability import get_logger, log_event
from ...domain.ports.disassembly import DisassemblyProducerFactory
from ...domain.ports.source_identity import SourceHashPort, SourceIdentityPort
from ...domain.ports.validation_dump import ValidationDumpFactory
from ..generation import (
    GenerationComponentOptions,
    GenerationFacade,
    GenerationRuntime,
    build_generation_runtime,
    resolve_explicit_validation_dump,
)
from .generation_contracts import GenerationRequest, HeaderBundle
from .session import DwarfSessionFactory

logger = get_logger(__name__)


class DwarfGenerator:
    """Coordinate one ELF/DWARF session and its typed generation workflow."""

    def __init__(
        self,
        elf_path: Path,
        session_factory: DwarfSessionFactory,
        exhaustive_search: bool = False,
        dwarf_dump_path: Path | None = None,
        dwarf_index_path: Path | None = None,
        resolve_param_names: bool = False,
        dump_lookup_factory: ValidationDumpFactory | None = None,
        disassembly_factory: DisassemblyProducerFactory | None = None,
        cache_file: Path | None = None,
        die_cache_size: int = 10000,
        type_cache_size: int = 5000,
        search_timeout: float = 1.0,
        source_hash: SourceHashPort | None = None,
        source_identity: SourceIdentityPort | None = None,
    ):
        """Initialize generator with ELF file path using lazy loading.

        Args:
            elf_path: Path to ELF file containing DWARF information
            session_factory: Composition-root factory for the ELF/DWARF session
            exhaustive_search: Enable exhaustive search mode (scan all CUs for best definition)
            dwarf_dump_path: Optional path to compressed llvm-dwarfdump .zst file for fast lookups
            dwarf_index_path: Optional explicit SQLite sidecar path for the dump index
            resolve_param_names: Enable method implementation search for parameter names (expensive)
        """
        self.session = session_factory(elf_path)
        self.elf_path = elf_path
        self.platform = self.session.platform
        self.exhaustive_search = exhaustive_search
        self._configured_dwarf_dump_path = dwarf_dump_path
        self.dwarf_dump_path = self._resolve_dwarf_dump_path()
        self.dwarf_index_path = dwarf_index_path
        self.resolve_param_names = resolve_param_names
        self.dump_lookup_factory = dump_lookup_factory
        self.disassembly_factory = disassembly_factory
        self.cache_file = cache_file
        self.die_cache_size = die_cache_size
        self.type_cache_size = type_cache_size
        self.search_timeout = search_timeout
        self.source_hash = source_hash
        self.source_identity = source_identity
        self.facade: GenerationFacade | None = None
        self._runtime: GenerationRuntime | None = None

    @property
    def runtime(self) -> GenerationRuntime:
        """Return the ready component graph for the open session."""
        if self._runtime is None:
            raise RuntimeError("generation runtime is unavailable outside an open session")
        return self._runtime

    def _resolve_dwarf_dump_path(self, explicit_path: Path | None = None) -> Path | None:
        return resolve_explicit_validation_dump(self._configured_dwarf_dump_path, explicit_path)

    def __enter__(self) -> DwarfGenerator:
        active_session = self.session.__enter__()
        started_at = perf_counter()
        try:
            runtime = build_generation_runtime(
                active_session,
                GenerationComponentOptions(
                    elf_path=self.elf_path,
                    exhaustive_search=self.exhaustive_search,
                    dwarf_dump_path=self.dwarf_dump_path,
                    dwarf_index_path=self.dwarf_index_path,
                    resolve_param_names=self.resolve_param_names,
                    dump_lookup_factory=self.dump_lookup_factory,
                    cache_file=self.cache_file,
                    die_cache_size=self.die_cache_size,
                    type_cache_size=self.type_cache_size,
                    search_timeout=self.search_timeout,
                    source_hash=self.source_hash,
                    source_identity=self.source_identity,
                ),
            )
            self._runtime = runtime
            self.platform = runtime.platform
            self.facade = GenerationFacade(runtime)
            log_event(
                logger,
                logging.INFO,
                "dwarf_generator_initialized",
                elf_path=self.elf_path,
                platform=self.platform.value,
                exhaustive_search=self.exhaustive_search,
                dump_lookup_enabled=self.dwarf_dump_path is not None,
                duration_ms=round((perf_counter() - started_at) * 1000, 3),
            )
            return self
        except Exception as error:
            log_event(
                logger,
                logging.ERROR,
                "dwarf_generator_initialization_failed",
                elf_path=self.elf_path,
                exc_info=error,
            )
            self._clear_components()
            try:
                self.session.close()
            except Exception as close_error:
                log_event(
                    logger,
                    logging.ERROR,
                    "dwarf_generator_cleanup_failed",
                    elf_path=self.elf_path,
                    exc_info=close_error,
                )
                raise error from close_error
            raise
        except BaseException as error:
            self._clear_components()
            try:
                self.session.close()
            except BaseException as close_error:
                log_event(
                    logger,
                    logging.ERROR,
                    "dwarf_generator_cleanup_failed",
                    elf_path=self.elf_path,
                    exc_info=close_error,
                )
                raise error from close_error
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        cache_error: Exception | None = None
        if self._runtime is not None:
            try:
                log_event(
                    logger,
                    logging.DEBUG,
                    "dwarf_cache_save_started",
                    path=self.cache_file,
                )
                self.save_cache()
                log_event(logger, logging.DEBUG, "dwarf_cache_saved", path=self.cache_file)
            except Exception as error:
                cache_error = error
                log_event(
                    logger,
                    logging.ERROR,
                    "dwarf_cache_save_failed",
                    path=self.cache_file,
                    exc_info=error,
                )
        close_error: BaseException | None = None
        try:
            self.session.__exit__(exc_type, exc_val, exc_tb)
        except BaseException as error:
            close_error = error
            log_event(
                logger,
                logging.ERROR,
                "dwarf_generator_cleanup_failed",
                elf_path=self.elf_path,
                exc_info=error,
            )
        finally:
            self._clear_components()
        if exc_val is not None:
            return None
        if close_error is not None:
            if cache_error is not None:
                raise cache_error from close_error
            raise close_error
        if cache_error is not None:
            raise cache_error
        return None

    def _clear_components(self) -> None:
        self._runtime = None
        self.facade = None

    def save_cache(self) -> None:
        """Persist the ready lookup component through the lifecycle boundary."""
        self.runtime.lazy_index.save_cache()

    def begin_root(self, root_symbol: str) -> None:
        """Start one root-scoped generation request in the owned session."""
        self.session.begin_root(root_symbol)

    def end_root(self) -> None:
        """Finish one root-scoped generation request in the owned session."""
        self.session.end_root()

    def generate(self, symbol: str, **options: bool) -> str:
        """Generate one header using a typed request."""
        request = GenerationRequest(
            symbol=symbol,
            full_hierarchy=options.get("full_hierarchy", False),
            single_file=True,
            include_metadata=not options.get("no_metadata", False),
        )
        return self.generate_bundle(request).only()

    def generate_bundle(self, request: GenerationRequest) -> HeaderBundle:
        """Run one typed workflow and adapt its result to a header bundle."""
        facade = self.facade
        if facade is None:
            raise RuntimeError("generation facade is unavailable outside an open session")
        return facade.generate(request)

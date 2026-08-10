"""Session and component setup responsibilities for the generator."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from ...core.observability import get_logger, log_event
from ...domain.ports.class_parser import ClassParserPort
from ...domain.services.generation import HeaderGenerator, HierarchyBuilder

logger = get_logger(__name__)


class DwarfGeneratorSetup:
    """Perform generator setup against an explicitly supplied host object."""

    @staticmethod
    def _resolve_dwarf_dump_path(generator: Any, explicit_path: Path | None = None) -> Path | None:
        """Resolve the configured or adjacent compressed DWARF dump."""
        if not getattr(generator.session, "legacy_lookup_allowed", True):
            return None
        candidate_path = explicit_path or generator._configured_dwarf_dump_path
        if candidate_path is not None or not generator.exhaustive_search:
            return candidate_path
        environment_path = os.getenv("DDON_DWARF_DUMP_PATH")
        if environment_path and (candidate := Path(environment_path)).exists():
            return candidate
        sibling = generator.elf_path.with_name(f"{generator.elf_path.name}.llvmdwarfdump.zst")
        return sibling if sibling.exists() else None

    @staticmethod
    def enter(generator: Any) -> Any:
        """Open the session and initialize all generation components."""
        active_session = generator.session.__enter__()
        generator.dwarf_info = active_session.dwarf_info
        generator.platform = active_session.platform
        try:
            started_at = perf_counter()
            DwarfGeneratorSetup.initialize_components(generator)
            log_event(
                logger,
                logging.INFO,
                "dwarf_generator_initialized",
                elf_path=generator.elf_path,
                platform=generator.platform.value,
                exhaustive_search=generator.exhaustive_search,
                dump_lookup_enabled=generator.dwarf_dump_path is not None,
                duration_ms=round((perf_counter() - started_at) * 1000, 3),
            )
            return generator
        except Exception as error:
            log_event(
                logger,
                logging.ERROR,
                "dwarf_generator_initialization_failed",
                elf_path=generator.elf_path,
                exc_info=error,
            )
            generator.session.close()
            generator.dwarf_info = None
            raise
        except BaseException:
            generator.session.close()
            generator.dwarf_info = None
            raise

    @staticmethod
    def exit(
        generator: Any,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Save the persistent cache and close the owned session."""
        try:
            if generator.lazy_index is not None:
                log_event(
                    logger,
                    logging.DEBUG,
                    "dwarf_cache_save_started",
                    path=generator.cache_file,
                )
                generator.lazy_index.save_cache()
                log_event(logger, logging.DEBUG, "dwarf_cache_saved", path=generator.cache_file)
        except Exception as error:
            log_event(
                logger,
                logging.ERROR,
                "dwarf_cache_save_failed",
                path=generator.cache_file,
                exc_info=error,
            )
            raise
        finally:
            generator.session.__exit__(exc_type, exc_val, exc_tb)
            generator.dwarf_info = None

    @staticmethod
    def initialize_components(generator: Any) -> None:
        """Initialize components in dependency order."""
        DwarfGeneratorSetup._initialize_lazy_index(generator)
        DwarfGeneratorSetup._initialize_type_resolver(generator)
        DwarfGeneratorSetup._initialize_class_parser(generator)
        DwarfGeneratorSetup._initialize_header_generator(generator)
        DwarfGeneratorSetup._initialize_hierarchy_builder(generator)

    @staticmethod
    def _initialize_lazy_index(generator: Any) -> None:
        assert generator.dwarf_info is not None, "dwarf_info must be initialized"
        started_at = perf_counter()
        store = getattr(generator.session, "store", None)
        provided_index = getattr(generator.session, "query_index", None)
        if store is not None and provided_index is not None:
            generator.lazy_index = provided_index
        else:
            from ...domain.services.lazy_dwarf_index_service import LazyDwarfIndexService

            generator.lazy_index = LazyDwarfIndexService(
                generator.dwarf_info,
                str(generator.cache_file or Path(".dwarf_cache.json")),
                die_cache_size=generator.die_cache_size,
                type_cache_size=generator.type_cache_size,
                search_timeout=generator.search_timeout,
                source_file_path=generator.elf_path,
                source_identity=generator.source_identity,
            )
        DwarfGeneratorSetup._log_component("lazy_index", started_at)

    @staticmethod
    def _initialize_type_resolver(generator: Any) -> None:
        from ...domain.services.parsing.type_resolver import LazyTypeResolver

        assert generator.dwarf_info is not None and generator.lazy_index is not None
        started_at = perf_counter()
        generator.type_resolver = LazyTypeResolver(generator.dwarf_info, generator.lazy_index)
        DwarfGeneratorSetup._log_component("type_resolver", started_at)

    @staticmethod
    def _initialize_class_parser(generator: Any) -> None:
        from ...domain.services.parsing import ClassParser

        assert generator.dwarf_info is not None and generator.lazy_index is not None
        assert generator.type_resolver is not None
        started_at = perf_counter()
        dump_parser = (
            generator.dump_lookup_factory(generator.dwarf_dump_path, generator.dwarf_index_path)
            if generator.dump_lookup_factory is not None and generator.dwarf_dump_path is not None
            else None
        )
        generator.class_parser = cast(
            ClassParserPort,
            ClassParser(
                generator.type_resolver,
                generator.dwarf_info,
                generator.lazy_index,
                exhaustive_search=generator.exhaustive_search,
                dwarf_dump_path=generator.dwarf_dump_path,
                dwarf_index_path=generator.dwarf_index_path,
                query_port=getattr(generator.session, "query_port", None),
                resolve_param_names=generator.resolve_param_names,
                dump_parser=dump_parser,
            ),
        )
        DwarfGeneratorSetup._log_component("class_parser", started_at)

    @staticmethod
    def _initialize_header_generator(generator: Any) -> None:
        assert generator.lazy_index is not None and generator.class_parser is not None
        started_at = perf_counter()
        generator.header_generator = HeaderGenerator(generator.lazy_index, generator.class_parser)
        DwarfGeneratorSetup._log_component("header_generator", started_at)

    @staticmethod
    def _initialize_hierarchy_builder(generator: Any) -> None:
        assert generator.lazy_index is not None and generator.class_parser is not None
        started_at = perf_counter()
        generator.hierarchy_builder = HierarchyBuilder(generator.class_parser, generator.lazy_index)
        DwarfGeneratorSetup._log_component("hierarchy_builder", started_at)

    @staticmethod
    def _log_component(component: str, started_at: float) -> None:
        log_event(
            logger,
            logging.DEBUG,
            "dwarf_component_initialized",
            component=component,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
        )

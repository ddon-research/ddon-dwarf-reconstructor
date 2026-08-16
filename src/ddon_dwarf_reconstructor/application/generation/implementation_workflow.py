"""Application orchestration for additive post-header implementation reports."""

from __future__ import annotations

from collections.abc import Mapping
from logging import Logger
from pathlib import Path
from typing import Protocol

from ...core.observability import bind_context, log_event, log_exception
from ...core.platform import ELFPlatform
from ...domain.models.implementation_evidence import (
    ImplementationDiscoveryReport,
    ImplementationStatus,
)
from ..generators import DwarfGenerator, HeaderBundle
from .options import GenerationOptions


class ImplementationReportState(Protocol):
    """Minimal state surface needed by the separate report publisher."""

    implementation_inputs: list[tuple[int, str, dict[str, str]]]
    implementation_reports: list[tuple[int, str, ImplementationDiscoveryReport]]


class ImplementationReportPublisher(Protocol):
    """Atomic report publication boundary supplied by the composition root."""

    def publish(
        self,
        output_root: Path,
        platform: ELFPlatform,
        index: int,
        symbol: str,
        report: ImplementationDiscoveryReport,
        *,
        emit_sources: bool = False,
        headers: Mapping[str, str] | None = None,
    ) -> Path: ...


def discover_implementations(
    options: GenerationOptions,
    generator: DwarfGenerator,
    symbol_name: str,
    headers: Mapping[str, str],
    logger: Logger,
) -> ImplementationDiscoveryReport:
    """Run additive discovery while keeping header success independent."""
    bundle = HeaderBundle(headers)
    try:
        return generator.discover_implementations(
            symbol_name,
            bundle,
            orbis_objdump_path=options.orbis_objdump,
        )
    except Exception as error:
        log_exception(logger, "implementation_discovery_failed", error, symbol=symbol_name)
        return ImplementationDiscoveryReport(
            symbol_name,
            bundle.sha256,
            ImplementationStatus.UNAVAILABLE,
            (),
            diagnostics=(f"implementation discovery failed: {error}",),
        )


def discover_implementations_after_headers(
    options: GenerationOptions,
    generator: DwarfGenerator,
    logger: Logger,
    state: ImplementationReportState,
) -> None:
    """Run the additive chain only after the complete header publication barrier."""
    for index, symbol_name, headers in state.implementation_inputs:
        with bind_context(symbol=symbol_name, symbol_index=index):
            root_started = False
            try:
                generator.begin_root(symbol_name)
                root_started = True
                report = discover_implementations(options, generator, symbol_name, headers, logger)
            except Exception as error:  # pragma: no cover - final lifecycle isolation boundary
                log_exception(
                    logger, "implementation_discovery_isolated_failure", error, symbol=symbol_name
                )
                report = ImplementationDiscoveryReport(
                    symbol_name,
                    HeaderBundle(headers).sha256,
                    ImplementationStatus.UNAVAILABLE,
                    (),
                    diagnostics=(f"implementation discovery isolated failure: {error}",),
                )
            finally:
                if root_started:
                    try:
                        generator.end_root()
                    except Exception as error:  # pragma: no cover - defensive lifecycle boundary
                        log_exception(
                            logger,
                            "implementation_discovery_root_close_failed",
                            error,
                            symbol=symbol_name,
                        )
            state.implementation_reports.append((index, symbol_name, report))


def publish_implementation_reports(
    output_root: Path,
    platform: ELFPlatform,
    logger: Logger,
    state: ImplementationReportState,
    publisher: ImplementationReportPublisher,
    *,
    emit_sources: bool = False,
) -> None:
    """Publish reports separately, without changing the header manifest."""
    if not state.implementation_reports:
        return
    published = 0
    for index, symbol_name, report in state.implementation_reports:
        try:
            headers = _headers_for(state, index, symbol_name)
            if emit_sources:
                path = publisher.publish(
                    output_root,
                    platform,
                    index,
                    symbol_name,
                    report,
                    emit_sources=True,
                    headers=headers,
                )
            else:
                path = publisher.publish(output_root, platform, index, symbol_name, report)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            log_exception(
                logger,
                "implementation_report_publish_failed",
                error,
                symbol=symbol_name,
            )
            continue
        published += 1
        log_event(
            logger,
            20,
            "implementation_report_published",
            symbol=symbol_name,
            path=path,
            status=report.status.value,
            method_count=len(report.methods),
        )
    log_event(
        logger,
        20 if published == len(state.implementation_reports) else 30,
        "implementation_reports_completed",
        report_count=len(state.implementation_reports),
        published_count=published,
    )


def _headers_for(
    state: ImplementationReportState, index: int, symbol_name: str
) -> Mapping[str, str] | None:
    for item_index, item_symbol, headers in state.implementation_inputs:
        if item_index == index and item_symbol == symbol_name:
            return headers
    return None


__all__ = [
    "discover_implementations",
    "discover_implementations_after_headers",
    "publish_implementation_reports",
]

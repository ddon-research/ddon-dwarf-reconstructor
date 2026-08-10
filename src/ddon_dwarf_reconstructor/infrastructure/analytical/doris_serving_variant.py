"""Typed source-bound identity for one Doris serving configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .doris_optimization_utils import configured_ddl_sha256 as _configured_ddl_sha256


@dataclass(frozen=True, slots=True)
class DorisServingVariant:
    """Source-bound physical serving identity used by benchmark evidence."""

    variant_id: str
    database: str
    base_table: str
    source_id: str | None
    schema_version: str | None
    ddl_sha256: str | None
    configuration_sha256: str
    index_policy: str = "canonical"
    storage_format: str = "V2"
    compression: str = "zstd"
    statistics_policy: str = "selective"
    reference_prefetch: str = "eager"
    attribute_projection: str = "full"
    child_tag_filter: str = "all"
    hydration_scope: str = "global"
    load_workers: int = 1

    def __post_init__(self) -> None:
        for field_name, value in (
            ("variant_id", self.variant_id),
            ("database", self.database),
            ("base_table", self.base_table),
            ("configuration_sha256", self.configuration_sha256),
        ):
            if not value.strip():
                raise ValueError(f"serving variant {field_name} must not be empty")
        if self.load_workers < 1:
            raise ValueError("serving variant load_workers must be positive")
        if self.reference_prefetch not in {"eager", "lazy"}:
            raise ValueError("serving variant reference_prefetch must be eager or lazy")
        if self.attribute_projection not in {"full", "serving"}:
            raise ValueError("serving variant attribute_projection must be full or serving")
        if self.child_tag_filter not in {"all", "targeted"}:
            raise ValueError("serving variant child_tag_filter must be all or targeted")
        if self.hydration_scope not in {"global", "unit"}:
            raise ValueError("serving variant hydration_scope must be global or unit")

    @classmethod
    def from_config(
        cls,
        config: Any,
        *,
        source_id: str | None = None,
        schema_version: str | None = None,
        ddl_sha256: str | None = None,
        variant_id: str | None = None,
    ) -> DorisServingVariant:
        """Build a stable identity from a Doris connection configuration."""
        statistics_policy = getattr(config, "statistics_policy", "selective")
        settings = {
            "database": config.database,
            "base_table": config.table,
            "definition_lookup_table": config.definition_lookup_table,
            "name_lookup_table": config.name_lookup_table,
            "method_lookup_table": config.method_lookup_table,
            "die_lookup_table": config.die_lookup_table,
            "statistics_policy": statistics_policy,
            "reference_prefetch": getattr(config, "reference_prefetch", "eager"),
            "attribute_projection": getattr(config, "attribute_projection", "full"),
            "child_tag_filter": getattr(config, "child_tag_filter", "all"),
            "hydration_scope": getattr(config, "hydration_scope", "global"),
            "stream_load_workers": config.stream_load_workers,
            "analyze_wait_seconds": config.analyze_wait_seconds,
        }
        configuration_sha256 = sha256(
            json.dumps(settings, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(
            variant_id or getattr(config, "serving_variant_id", "canonical"),
            config.database,
            config.table,
            source_id,
            schema_version,
            ddl_sha256 or _configured_ddl_sha256(config),
            configuration_sha256,
            statistics_policy=statistics_policy,
            reference_prefetch=getattr(config, "reference_prefetch", "eager"),
            attribute_projection=getattr(config, "attribute_projection", "full"),
            child_tag_filter=getattr(config, "child_tag_filter", "all"),
            hydration_scope=getattr(config, "hydration_scope", "global"),
            load_workers=config.stream_load_workers,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "variant_id": self.variant_id,
            "database": self.database,
            "base_table": self.base_table,
            "source_id": self.source_id,
            "schema_version": self.schema_version,
            "ddl_sha256": self.ddl_sha256,
            "configuration_sha256": self.configuration_sha256,
            "index_policy": self.index_policy,
            "storage_format": self.storage_format,
            "compression": self.compression,
            "statistics_policy": self.statistics_policy,
            "reference_prefetch": self.reference_prefetch,
            "attribute_projection": self.attribute_projection,
            "child_tag_filter": self.child_tag_filter,
            "hydration_scope": self.hydration_scope,
            "load_workers": self.load_workers,
        }


__all__ = ["DorisServingVariant"]

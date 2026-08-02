from __future__ import annotations

from pathlib import Path

import pytest

from dwarf_spec_pipeline.models import SourceLocation
from dwarf_spec_pipeline.source_manifest import SourceSpec


@pytest.fixture
def source() -> SourceSpec:
    return SourceSpec(
        source_id="dwarf2",
        standard_version=2,
        title="DWARF Version 2",
        filename="dwarf.v2.mm",
        format="mm",
        url="https://dwarfstd.org/doc/dwarf.v2.mm",
        source_page="https://dwarfstd.org/doc/",
        sha256="0" * 64,
    )


@pytest.fixture
def source_location() -> SourceLocation:
    return SourceLocation(source_id="dwarf2", intermediate="html", block_index=7)


@pytest.fixture
def schema_path() -> Path:
    return Path(__file__).parent.parent / "schema" / "dwarf-specification.schema.json"

"""CFI acquisition remains an infrastructure evidence boundary."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.domain.models.implementation_validation import ValidationStatus
from ddon_dwarf_reconstructor.infrastructure import implementation_cfi

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_cfi_boundary_join_keeps_incomplete_rows_non_promoting() -> None:
    from ddon_dwarf_reconstructor.infrastructure.implementation_dwarf_context import (
        store_cfi_status,
    )

    observed = store_cfi_status(
        (
            {"parser_status": "complete", "initial_address": 0x100},
            {"parser_status": "complete", "initial_address": 0x120},
        ),
        (),
    )
    partial = store_cfi_status(({"parser_status": "partial"},), ())
    assert observed.status is ValidationStatus.OBSERVED
    assert observed.details["covering_entries"] == 2
    assert partial.status is ValidationStatus.PARTIAL


def test_cfi_inspection_reports_empty_unavailable_and_observed_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert (
        implementation_cfi.inspect_cfi(tmp_path / "missing.elf", 0, 0).status
        is ValidationStatus.NOT_OBSERVED
    )
    missing = implementation_cfi.inspect_cfi(tmp_path / "missing.elf", 0, 8)
    assert missing.status is ValidationStatus.UNAVAILABLE

    class Entry:
        header = {"initial_location": 0x100, "address_range": 0x20}

    class Dwarf:
        def CFI_entries(self) -> tuple[Entry, ...]:  # noqa: N802
            return (Entry(),)

        def EH_CFI_entries(self) -> tuple[Entry, ...]:  # noqa: N802
            return ()

    class FakeElf:
        def get_dwarf_info(self) -> Dwarf:
            return Dwarf()

    source = tmp_path / "cfi.elf"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(implementation_cfi, "ELFFile", lambda _stream: FakeElf())
    observed = implementation_cfi.inspect_cfi(source, 0x110, 4)
    assert observed.status is ValidationStatus.OBSERVED

    class GapDwarf:
        def CFI_entries(self) -> tuple[object, ...]:  # noqa: N802
            return (SimpleNamespace(header={"initial_location": 0x100, "address_range": 4}),)

        def EH_CFI_entries(self) -> tuple[object, ...]:  # noqa: N802
            return ()

    monkeypatch.setattr(
        implementation_cfi,
        "ELFFile",
        lambda _stream: SimpleNamespace(get_dwarf_info=lambda: GapDwarf()),
    )
    partial = implementation_cfi.inspect_cfi(source, 0x100, 8)
    assert partial.status is ValidationStatus.PARTIAL
    assert partial.details["uncovered_ranges"] == ((0x104, 0x108),)

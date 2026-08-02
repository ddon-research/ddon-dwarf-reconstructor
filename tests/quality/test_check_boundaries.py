from __future__ import annotations

from pathlib import Path

from tests.support.quality.check_boundaries import check


def test_domain_infrastructure_import_is_reported(tmp_path: Path) -> None:
    package = tmp_path / "ddon_dwarf_reconstructor" / "domain"
    package.mkdir(parents=True)
    source = package / "service.py"
    source.write_text(
        "from ddon_dwarf_reconstructor.infrastructure import artifacts\n",
        encoding="utf-8",
    )

    assert check(tmp_path / "ddon_dwarf_reconstructor") == [
        f"{source}: domain imports ddon_dwarf_reconstructor.infrastructure"
    ]


def test_application_imports_are_checked(tmp_path: Path) -> None:
    package = tmp_path / "ddon_dwarf_reconstructor" / "application"
    package.mkdir(parents=True)
    source = package / "service.py"
    source.write_text(
        "from ddon_dwarf_reconstructor.infrastructure import artifacts\n",
        encoding="utf-8",
    )

    assert check(tmp_path / "ddon_dwarf_reconstructor") == [
        f"{source}: application imports ddon_dwarf_reconstructor.infrastructure"
    ]


def test_relative_adapter_imports_are_checked_but_logging_is_allowed(tmp_path: Path) -> None:
    package = tmp_path / "ddon_dwarf_reconstructor" / "domain"
    package.mkdir(parents=True)
    source = package / "service.py"
    source.write_text(
        "from ...infrastructure.logging import get_logger\n"
        "from ...infrastructure.zstd_dump_parser import ZstdDumpParser\n",
        encoding="utf-8",
    )

    assert check(tmp_path / "ddon_dwarf_reconstructor") == [
        f"{source}: domain imports infrastructure.zstd_dump_parser"
    ]


def test_application_composition_import_is_allowed_but_adapters_are_not(tmp_path: Path) -> None:
    package = tmp_path / "ddon_dwarf_reconstructor" / "application"
    package.mkdir(parents=True)
    source = package / "service.py"
    source.write_text(
        "from ...infrastructure.composition import create_dump_lookup\n"
        "from ...infrastructure.orbis_objdump import OrbisObjdumpProducer\n",
        encoding="utf-8",
    )

    assert check(tmp_path / "ddon_dwarf_reconstructor") == [
        f"{source}: application imports infrastructure.orbis_objdump"
    ]

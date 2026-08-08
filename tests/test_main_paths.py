"""Typed generation workflow helpers and failure-path coverage."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generators import HeaderBundle
from ddon_dwarf_reconstructor.infrastructure.elf_platform import ELFPlatform
from ddon_dwarf_reconstructor.main import GenerationOptions

cli_main = importlib.import_module("ddon_dwarf_reconstructor.main")


def _options(**overrides: object) -> GenerationOptions:
    values: dict[str, object] = {
        "elf_file": Path("resources/DDOORBIS.elf"),
        "symbols": ("A",),
        "symbols_file": None,
        "output": None,
        "verbose": False,
        "full_hierarchy": False,
        "single_file": False,
        "exhaustive": False,
        "dwarf_dump": None,
        "dwarf_index": None,
        "export_knowledge": None,
        "build_id": None,
        "orbis_objdump": None,
        "resolve_param_names": False,
    }
    values.update(overrides)
    return GenerationOptions(**values)  # type: ignore[arg-type]


@pytest.mark.unit
def test_generation_mode_reports_single_and_multi_file_modes() -> None:
    assert cli_main._generation_mode(_options()) == "single-header"
    assert cli_main._generation_mode(_options(full_hierarchy=True, single_file=True)).startswith(
        "full-hierarchy (single-file"
    )
    assert cli_main._generation_mode(_options(full_hierarchy=True)).endswith("multi-file)")


@pytest.mark.unit
def test_read_symbols_accepts_repeated_options_and_rejects_invalid_combinations(
    tmp_path: Path,
) -> None:
    logger = Mock()
    symbols_file = tmp_path / "symbols.txt"
    symbols_file.write_text("# comment\nA\n\n B \n", encoding="utf-8")

    assert cli_main._read_symbols(_options(symbols=(), symbols_file=symbols_file), logger) == [
        "A",
        "B",
    ]
    conflicting_options = _options(symbols=("A",), symbols_file=symbols_file)
    with pytest.raises(ValueError, match="both"):
        cli_main._read_symbols(conflicting_options, logger)
    missing_source_options = _options(symbols=(), symbols_file=None)
    with pytest.raises(ValueError, match="either"):
        cli_main._read_symbols(missing_source_options, logger)
    empty_symbol_options = _options(symbols=("",), symbols_file=None)
    with pytest.raises(ValueError, match="No symbols"):
        cli_main._read_symbols(empty_symbol_options, logger)

    duplicate_options = _options(symbols=("A", "A"), symbols_file=None)
    with pytest.raises(ValueError, match="Duplicate symbol"):
        cli_main._read_symbols(duplicate_options, logger)


@pytest.mark.unit
def test_season2_resource_corpus_has_289_unique_roots() -> None:
    symbols = cli_main._read_symbols(
        _options(symbols=(), symbols_file=Path("resources/season2-resources.txt")), Mock()
    )

    assert len(symbols) == 289
    assert len(set(symbols)) == 289


@pytest.mark.unit
def test_read_symbols_reports_missing_files(tmp_path: Path) -> None:
    options = _options(symbols=(), symbols_file=tmp_path / "missing")
    logger = Mock()
    with pytest.raises(ValueError, match="not found"):
        cli_main._read_symbols(options, logger)


@pytest.mark.unit
def test_build_headers_uses_typed_bundle_for_all_modes() -> None:
    generator = Mock()
    generator.generate_bundle.side_effect = [
        HeaderBundle.single("A", "single"),
        HeaderBundle.single("A", "complete"),
        HeaderBundle({"A.h": "multi", "B.h": "more"}),
    ]

    assert cli_main._build_headers(_options(), generator, "A") == {"A.h": "single"}
    assert cli_main._build_headers(
        _options(full_hierarchy=True, single_file=True), generator, "A"
    ) == {"A.h": "complete"}
    assert cli_main._build_headers(_options(full_hierarchy=True), generator, "A") == {
        "A.h": "multi",
        "B.h": "more",
    }


@pytest.mark.unit
def test_write_headers_uses_platform_directory_and_logs_success(tmp_path: Path) -> None:
    config = Mock(output_dir=tmp_path)
    generator = Mock(platform=ELFPlatform.PS4)
    logger = Mock()

    total = cli_main._write_headers(config, generator, {"A.h": "abc", "B.h": "de"}, logger)

    assert total == 5
    assert (tmp_path / "ps4" / "A.h").read_text(encoding="utf-8") == "abc"
    assert (tmp_path / "ps4" / "B.h").read_text(encoding="utf-8") == "de"


@pytest.mark.unit
def test_write_headers_does_not_publish_partial_bundle(tmp_path: Path, monkeypatch) -> None:
    import os

    from ddon_dwarf_reconstructor.infrastructure import header_output

    real_replace = os.replace

    def fail_second_header(source, destination):
        if Path(source).name == "B.h":
            raise OSError("interrupted publication")
        return real_replace(source, destination)

    monkeypatch.setattr(header_output.os, "replace", fail_second_header)
    publisher = header_output.AtomicHeaderPublisher()
    with pytest.raises(OSError, match="interrupted publication"):
        publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "a", "B.h": "b"})

    platform_dir = tmp_path / "ps4"
    assert not (platform_dir / "A.h").exists()
    assert not (platform_dir / "B.h").exists()
    assert not (platform_dir / "header-bundle.manifest.json").exists()


@pytest.mark.unit
def test_header_publisher_removes_files_from_previous_manifest(tmp_path: Path) -> None:
    from ddon_dwarf_reconstructor.infrastructure.header_output import AtomicHeaderPublisher

    publisher = AtomicHeaderPublisher()
    publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "a", "B.h": "b"})
    publisher.publish(tmp_path, ELFPlatform.PS4, {"A.h": "new"})

    platform_dir = tmp_path / "ps4"
    assert (platform_dir / "A.h").read_text(encoding="utf-8") == "new"
    assert not (platform_dir / "B.h").exists()


@pytest.mark.unit
def test_header_publisher_persists_generation_metadata(tmp_path: Path) -> None:
    import json

    from ddon_dwarf_reconstructor.infrastructure.header_output import AtomicHeaderPublisher

    AtomicHeaderPublisher().publish(
        tmp_path,
        ELFPlatform.PS4,
        {"A.h": "a"},
        metadata={
            "generation": {
                "requested_symbols": ["A"],
                "outcomes": [{"symbol": "A", "status": "success", "headers": ["A.h"]}],
                "published": True,
            }
        },
    )

    manifest = json.loads(
        (tmp_path / "ps4" / "header-bundle.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["metadata"]["generation"]["requested_symbols"] == ["A"]
    assert manifest["metadata"]["generation"]["published"] is True


@pytest.mark.unit
def test_process_symbol_saves_cache_after_header_output(tmp_path: Path) -> None:
    options = _options()
    config = Mock(output_dir=tmp_path, verbose=False)
    generator = Mock(platform=ELFPlatform.PS4)
    generator.generate_bundle.return_value = HeaderBundle.single("A", "header")
    generator.lazy_index = Mock()
    logger = Mock()

    cli_main._process_symbol(options, config, generator, "A", ["A"], logger)

    assert (tmp_path / "ps4" / "A.h").exists()
    generator.lazy_index.save_cache.assert_called_once_with()


@pytest.mark.unit
def test_run_generation_publishes_one_bundle_for_all_symbols(tmp_path: Path, mocker) -> None:
    config = Mock(
        output_dir=tmp_path,
        elf_file_path=Path("input.elf"),
        verbose=False,
    )
    generator = mocker.MagicMock(platform=ELFPlatform.PS4)
    generator.__enter__.return_value = generator
    generator.lazy_index = Mock()
    mocker.patch.object(
        cli_main.DwarfRuntimeConfig,
        "from_environment",
        return_value=Mock(die_cache_size=1, type_cache_size=1, search_timeout_seconds=1.0),
    )
    mocker.patch.object(cli_main, "SourceIdentityCatalog", return_value=Mock(sha256=Mock()))
    mocker.patch.object(cli_main, "get_cache_file_path", return_value=tmp_path / "cache.json")
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=generator)
    mocker.patch.object(
        cli_main,
        "_build_headers",
        side_effect=[{"A.h": "a"}, {"B.h": "bb"}],
    )
    publisher = mocker.patch.object(cli_main, "_write_headers", return_value=3)
    logger = Mock()

    success, failures = cli_main._run_generation(
        _options(symbols=("A", "B")), config, ["A", "B"], logger
    )

    assert success == 2
    assert failures == []
    publisher.assert_called_once_with(
        config,
        generator,
        {"A.h": "a", "B.h": "bb"},
        mocker.ANY,
        metadata=mocker.ANY,
    )
    report_calls = [
        call for call in logger.log.call_args_list if call.args[1] == "generation_report"
    ]
    assert len(report_calls) == 1
    fields = report_calls[0].kwargs["extra"]["ddon_fields"]
    assert fields["published"] is True
    assert fields["outcomes"] == [
        {"symbol": "A", "status": "success", "headers": ["A.h"]},
        {"symbol": "B", "status": "success", "headers": ["B.h"]},
    ]


@pytest.mark.unit
def test_run_generation_publishes_separate_bundles_for_full_hierarchy_roots(
    tmp_path: Path, mocker
) -> None:
    config = Mock(
        output_dir=tmp_path,
        elf_file_path=Path("input.elf"),
        verbose=False,
    )
    generator = mocker.MagicMock(platform=ELFPlatform.PS4)
    generator.__enter__.return_value = generator
    generator.lazy_index = Mock()
    mocker.patch.object(
        cli_main.DwarfRuntimeConfig,
        "from_environment",
        return_value=Mock(die_cache_size=1, type_cache_size=1, search_timeout_seconds=1.0),
    )
    mocker.patch.object(cli_main, "SourceIdentityCatalog", return_value=Mock(sha256=Mock()))
    mocker.patch.object(cli_main, "get_cache_file_path", return_value=tmp_path / "cache.json")
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=generator)
    mocker.patch.object(
        cli_main,
        "_build_headers",
        side_effect=[
            {"MtAllocator.h": "root A context"},
            {"MtAllocator.h": "root B context"},
        ],
    )
    publisher = mocker.patch.object(cli_main, "_write_headers", return_value=3)
    logger = Mock()

    success, failures = cli_main._run_generation(
        _options(symbols=("rAIFSM", "rZone"), full_hierarchy=True),
        config,
        ["rAIFSM", "rZone"],
        logger,
    )

    assert success == 2
    assert failures == []
    assert publisher.call_count == 2
    assert publisher.call_args_list[0].kwargs["output_dir"] == (
        tmp_path / "symbols" / "0001-rAIFSM"
    )
    assert publisher.call_args_list[1].kwargs["output_dir"] == tmp_path / "symbols" / "0002-rZone"
    assert publisher.call_args_list[0].args[2] == {"MtAllocator.h": "root A context"}
    assert publisher.call_args_list[1].args[2] == {"MtAllocator.h": "root B context"}
    report_calls = [
        call for call in logger.log.call_args_list if call.args[1] == "generation_report"
    ]
    assert len(report_calls) == 1
    fields = report_calls[0].kwargs["extra"]["ddon_fields"]
    assert fields["published"] is True

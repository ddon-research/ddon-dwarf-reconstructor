"""Typed generation workflow helpers and failure-path coverage."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.generation.logging_workflow import generation_mode
from ddon_dwarf_reconstructor.domain.models.implementation_evidence import (
    ImplementationDiscoveryReport,
    ImplementationStatus,
)
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
        "generate_context": True,
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
def test_generation_mode_uses_one_symbol_set_mode_for_every_generate_request() -> None:
    assert generation_mode(_options()) == "symbol-set"
    assert generation_mode(_options(symbols=("A", "B"))) == "symbol-set"
    assert generation_mode(_options(symbols=(), symbols_file=Path("symbols.txt"))) == ("symbol-set")
    assert generation_mode(_options(full_hierarchy=True)) == "symbol-set"


@pytest.mark.unit
def test_source_emission_requires_assembly_extraction() -> None:
    with pytest.raises(ValueError, match="requires --extract-assembly"):
        cli_main._validate_implementation_options(
            _options(emit_implementation_sources=True, extract_assembly=False)
        )


@pytest.mark.unit
def test_single_file_is_rejected_for_symbol_generation() -> None:
    with pytest.raises(ValueError, match="not supported"):
        cli_main._validate_implementation_options(_options(single_file=True))


@pytest.mark.unit
def test_symbol_generation_defaults_to_generated_output_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Mock(output_dir=Path("output"))
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    monkeypatch.setattr(cli_main.Config, "from_args", Mock(return_value=config))

    loaded = cli_main._load_config(_options())

    assert loaded.output_dir == Path("generated")
    config.validate.assert_called_once_with()


@pytest.mark.unit
def test_targeted_llvm_options_require_assembly_and_an_executable() -> None:
    with pytest.raises(ValueError, match="--orbis-objdump requires"):
        cli_main._validate_implementation_options(_options(orbis_objdump=Path("orbis-objdump")))
    with pytest.raises(ValueError, match="--llvm-objdump requires"):
        cli_main._validate_implementation_options(
            _options(llvm_objdump=Path("llvm-objdump"), extract_assembly=False)
        )
    with pytest.raises(ValueError, match="requires --llvm-objdump"):
        cli_main._validate_implementation_options(_options(llvm_target_triple="x86_64-pc-freebsd"))
    with pytest.raises(ValueError, match="--llvm-readobj requires"):
        cli_main._validate_implementation_options(
            _options(llvm_readobj=Path("llvm-readobj"), extract_assembly=False)
        )
    with pytest.raises(ValueError, match="require --orbis-objdump"):
        cli_main._validate_implementation_options(
            _options(
                llvm_objdump=Path("llvm-objdump"),
                extract_assembly=True,
            )
        )


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
def test_write_headers_uses_platform_directory_and_logs_success(tmp_path: Path) -> None:
    from ddon_dwarf_reconstructor.infrastructure.header_output import AtomicHeaderPublisher

    platform_dir, total = AtomicHeaderPublisher().publish(
        tmp_path,
        ELFPlatform.PS4,
        {"A.h": "abc", "B.h": "de"},
    )

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
def test_header_publisher_can_emit_clean_headers_without_context(tmp_path: Path) -> None:
    from ddon_dwarf_reconstructor.infrastructure.header_output import AtomicHeaderPublisher

    AtomicHeaderPublisher().publish(
        tmp_path,
        ELFPlatform.PS4,
        {"A.h": "a"},
        generate_context=False,
    )

    platform_dir = tmp_path / "ps4"
    assert tuple(platform_dir.glob("*.json")) == ()
    assert (platform_dir / "A.h").read_text(encoding="utf-8") == "a"


@pytest.mark.unit
def test_run_generation_uses_one_symbol_set_request_for_all_symbols(tmp_path: Path, mocker) -> None:
    config = Mock(
        output_dir=tmp_path,
        elf_file_path=Path("input.elf"),
        verbose=False,
    )
    generator = mocker.MagicMock(platform=ELFPlatform.PS4)
    generator.__enter__.return_value = generator
    mocker.patch.object(
        cli_main.DwarfRuntimeConfig,
        "from_environment",
        return_value=Mock(die_cache_size=1, type_cache_size=1, search_timeout_seconds=1.0),
    )
    mocker.patch.object(cli_main, "SourceIdentityCatalog", return_value=Mock(sha256=Mock()))
    mocker.patch.object(cli_main, "get_cache_file_path", return_value=tmp_path / "cache.json")
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=generator)
    symbol_runner = mocker.patch.object(cli_main, "_run_symbol_generation", return_value=(2, []))
    logger = Mock()

    success, failures = cli_main._run_generation(
        _options(symbols=("A", "B")), config, ["A", "B"], logger
    )

    assert success == 2
    assert failures == []
    symbol_runner.assert_called_once()


@pytest.mark.unit
def test_symbol_generation_discovers_assembly_once_after_one_union(tmp_path: Path, mocker) -> None:
    config = Mock(output_dir=tmp_path, elf_file_path=Path("input.elf"), verbose=False)
    generator = mocker.MagicMock(platform=ELFPlatform.PS4)
    symbol_set = Mock(
        headers={"A/A.h": "class A {};"},
        header_classes={"A/A.h": ("A",)},
        class_origins={"A": ("A",)},
        root_statuses={"A": "success"},
        header_count=1,
        class_count=1,
    )
    symbol_set.roots_for_header.return_value = ("A",)
    report = ImplementationDiscoveryReport(
        "symbols",
        "header-sha",
        ImplementationStatus.NOT_OBSERVED,
        (),
    )
    generator.extract_symbols.return_value = symbol_set
    generator.discover_implementations_for_symbols.return_value = report
    identity_catalog = Mock(sha256=Mock(return_value="elf-sha"))
    publisher = mocker.patch.object(cli_main, "SymbolPublisher")
    publisher.return_value.publish.return_value = tmp_path / "ps4-unknown"

    success, failures = cli_main._run_symbol_generation(
        _options(symbols=("A",), extract_assembly=True),
        config,
        generator,
        ["A"],
        Mock(),
        identity_catalog,
    )

    assert (success, failures) == (1, [])
    generator.extract_symbols.assert_called_once()
    generator.discover_implementations_for_symbols.assert_called_once_with(
        ("A",), symbol_set, orbis_objdump_path=None
    )
    assert publisher.return_value.publish.call_count == 2
    header_call, implementation_call = publisher.return_value.publish.call_args_list
    assert header_call.args[5] is None
    assert header_call.kwargs == {
        "emit_assembly": False,
        "emit_sources": False,
        "generate_context": True,
    }
    assert implementation_call.args[5] is report
    assert implementation_call.kwargs == {
        "emit_assembly": True,
        "emit_sources": False,
        "generate_context": True,
    }


@pytest.mark.unit
@pytest.mark.regression
def test_symbol_generation_propagates_partial_root_status(tmp_path: Path, mocker) -> None:
    config = Mock(output_dir=tmp_path, elf_file_path=Path("input.elf"), verbose=False)
    generator = mocker.MagicMock(platform=ELFPlatform.PS4)
    symbol_set = Mock(
        headers={"shared.h": "class A {}; class B {};"},
        header_classes={"shared.h": ("A", "B")},
        class_origins={"A": ("A",), "B": ("B",)},
        root_statuses={"A": "success", "B": "partial"},
        header_count=1,
        class_count=2,
    )
    symbol_set.roots_for_header.return_value = ("A", "B")
    generator.extract_symbols.return_value = symbol_set
    identity_catalog = Mock(sha256=Mock(return_value="elf-sha"))
    mocker.patch.object(cli_main, "SymbolPublisher").return_value.publish.return_value = (
        tmp_path / "ps4-unknown"
    )
    logged = mocker.patch.object(cli_main, "log_event")

    success, failures = cli_main._run_symbol_generation(
        _options(symbols=("A", "B")),
        config,
        generator,
        ["A", "B"],
        Mock(),
        identity_catalog,
    )

    assert success == 1
    assert failures == [("B", "generation status is partial")]
    report = next(
        call.kwargs["fields"] for call in logged.call_args_list if "fields" in call.kwargs
    )
    assert [outcome["status"] for outcome in report["outcomes"]] == ["success", "partial"]


@pytest.mark.unit
@pytest.mark.regression
def test_symbol_generation_publishes_headers_before_assembly_discovery(
    tmp_path: Path, mocker
) -> None:
    config = Mock(output_dir=tmp_path, elf_file_path=Path("input.elf"), verbose=False)
    generator = mocker.MagicMock(platform=ELFPlatform.PS4)
    symbol_set = Mock(
        headers={"A/A.h": "class A {};"},
        header_classes={"A/A.h": ("A",)},
        class_origins={"A": ("A",)},
        root_statuses={"A": "success"},
        header_count=1,
        class_count=1,
    )
    symbol_set.roots_for_header.return_value = ("A",)
    generator.extract_symbols.return_value = symbol_set
    identity_catalog = Mock(sha256=Mock(return_value="elf-sha"))
    publish = mocker.patch.object(cli_main, "SymbolPublisher").return_value.publish
    publish.return_value = tmp_path / "ps4-unknown"

    def fail_discovery(*_args, **_kwargs):
        assert publish.call_count == 1
        raise RuntimeError("disassembly failed")

    generator.discover_implementations_for_symbols.side_effect = fail_discovery

    with pytest.raises(RuntimeError, match="disassembly failed"):
        cli_main._run_symbol_generation(
            _options(symbols=("A",), extract_assembly=True),
            config,
            generator,
            ["A"],
            Mock(),
            identity_catalog,
        )

    assert publish.call_count == 1
    assert publish.call_args.args[5] is None
    assert publish.call_args.kwargs["emit_assembly"] is False
    assert publish.call_args.kwargs["emit_sources"] is False


@pytest.mark.unit
def test_run_generation_does_not_publish_separate_root_bundles(tmp_path: Path, mocker) -> None:
    config = Mock(
        output_dir=tmp_path,
        elf_file_path=Path("input.elf"),
        verbose=False,
    )
    generator = mocker.MagicMock(platform=ELFPlatform.PS4)
    generator.__enter__.return_value = generator
    mocker.patch.object(
        cli_main.DwarfRuntimeConfig,
        "from_environment",
        return_value=Mock(die_cache_size=1, type_cache_size=1, search_timeout_seconds=1.0),
    )
    mocker.patch.object(cli_main, "SourceIdentityCatalog", return_value=Mock(sha256=Mock()))
    mocker.patch.object(cli_main, "get_cache_file_path", return_value=tmp_path / "cache.json")
    mocker.patch.object(cli_main, "DwarfGenerator", return_value=generator)
    symbol_runner = mocker.patch.object(cli_main, "_run_symbol_generation", return_value=(2, []))
    logger = Mock()

    success, failures = cli_main._run_generation(
        _options(symbols=("rAIFSM", "rZone"), full_hierarchy=True),
        config,
        ["rAIFSM", "rZone"],
        logger,
    )

    assert success == 2
    assert failures == []
    symbol_runner.assert_called_once()

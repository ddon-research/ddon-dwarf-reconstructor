"""Tests for bounded, cached PS4 Orbis disassembly."""

from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import Mock

import pytest

import ddon_dwarf_reconstructor.infrastructure.orbis_objdump as orbis
from ddon_dwarf_reconstructor.infrastructure.orbis_objdump import (
    OrbisFunctionSymbol,
    OrbisObjdumpProducer,
)

SYMBOLS = """\
0000000000693e60 g     F .text  0000000000000c85 rLayout::load(MtStream&)
0000000000694af0 g     F .text  0000000000000010 rLayout::getExt() const
000000000069b680 g     F .text  00000000000000e5 rLayoutGroupParam::load(MtStream&)
"""

DISASSEMBLY = """\
Disassembly of section .text:

0000000000693e60 <rLayout::load(MtStream&)>:
load():
D:\\build\\rLayout.cpp:176
  693e60:\t55                   \tpush   %rbp
  693e61:\te8 6a f7 ff ff       \tcallq  6935d0 <rLayout::destruct()>
D:\\build\\rLayout.cpp:181
  693e66:\tff 51 40             \tcallq  *0x40(%rcx)
  694af0:\tc3                   \tretq
"""


@pytest.mark.unit
def test_symbol_selection_is_class_scoped() -> None:
    symbols = OrbisObjdumpProducer.parse_symbols(SYMBOLS)

    selected = OrbisObjdumpProducer.select_root_symbols(symbols, "rLayout")

    assert [symbol.name for symbol in selected] == [
        "rLayout::load(MtStream&)",
        "rLayout::getExt() const",
    ]
    assert selected[0].address == 0x693E60
    assert selected[0].end_address == 0x694AE5


@pytest.mark.unit
def test_instruction_parser_preserves_lines_bytes_and_direct_calls() -> None:
    instructions = OrbisObjdumpProducer.parse_instructions(DISASSEMBLY)

    assert len(instructions) == 4
    assert instructions[0].raw_bytes == "55"
    assert instructions[0].source_file == r"D:\build\rLayout.cpp"
    assert instructions[0].source_line == 176
    assert instructions[1].call_target_address == 0x6935D0
    assert instructions[1].call_target_name == "rLayout::destruct()"
    assert instructions[2].call_target_address is None
    assert instructions[2].source_line == 181


class StubOrbisProducer(OrbisObjdumpProducer):
    """Supply deterministic command output without starting an SDK process."""

    def __init__(self, executable: Path, cache_root: Path) -> None:
        super().__init__(executable, cache_root=cache_root)
        self.calls: list[tuple[str, ...]] = []

    def _run(self, arguments: list[str]) -> str:
        self.calls.append(tuple(arguments))
        if arguments == ["--version"]:
            return "GNU objdump (GNU Binutils) 2.22 (Orbis version 8.00.0.398 f8fc24e5)\n"
        if arguments[0] == "-f":
            return "fixture: file format elf64-x86-64-freebsd\n"
        if arguments[0] == "-t":
            return SYMBOLS
        if arguments[0] == "-EL":
            return DISASSEMBLY
        raise AssertionError(arguments)


@pytest.mark.unit
def test_report_cache_skips_warm_symbol_and_disassembly_runs(tmp_path: Path) -> None:
    executable = tmp_path / "orbis-objdump.exe"
    executable.write_bytes(b"orbis tool fixture")
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"orbis elf fixture")
    cache_root = tmp_path / "cache"
    cold = StubOrbisProducer(executable, cache_root)

    first = cold.produce(elf_path, "rLayout")
    warm = StubOrbisProducer(executable, cache_root)
    second = warm.produce(elf_path, "rLayout")

    assert first == second
    assert cold.last_cache_hit is False
    assert warm.last_cache_hit is True
    assert sum(1 for call in cold.calls if call[0] == "-t") == 1
    assert sum(1 for call in cold.calls if call[0] == "-EL") == 1
    assert not any(call[0] in {"-t", "-EL"} for call in warm.calls)


@pytest.mark.unit
def test_symbol_parser_filters_malformed_non_function_and_zero_size_rows() -> None:
    output = "\n".join(
        [
            "not a symbol",
            "1 2 O .text 3 ignored",
            "zz 2 F .text 4 bad-address",
            "1 2 F .text zz bad-size",
            "1 2 F .text 0 zero-size",
            "1 2 F .text 4 valid()",
        ]
    )

    symbols = OrbisObjdumpProducer.parse_symbols(output)

    assert symbols == (OrbisFunctionSymbol(1, 4, ".text", "valid()"),)


@pytest.mark.unit
def test_symbol_selection_supports_thunks_and_rejects_unrelated_names() -> None:
    symbols = (
        OrbisFunctionSymbol(1, 2, ".text", "virtual thunk to rLayout::load()"),
        OrbisFunctionSymbol(3, 2, ".text", "non-virtual thunk to rLayout::get()"),
        OrbisFunctionSymbol(5, 2, ".text", "rOther::load()"),
    )

    assert [
        symbol.address for symbol in OrbisObjdumpProducer.select_root_symbols(symbols, "rLayout")
    ] == [
        1,
        3,
    ]


@pytest.mark.unit
def test_instruction_parser_skips_incomplete_rows_and_keeps_indirect_calls_unresolved() -> None:
    output = "\n".join(
        [
            "source.cpp:not-a-line",
            "  10:\t55",
            "  11:\t55                   \tcallq  *%rax",
            "  12:\t55                   \tadd %rax,%rbx",
        ]
    )

    instructions = OrbisObjdumpProducer.parse_instructions(output)

    assert [item.address for item in instructions] == [0x11, 0x12]
    assert instructions[0].call_target_address is None


@pytest.mark.unit
def test_orbis_command_and_metadata_errors_are_specific() -> None:
    producer = OrbisObjdumpProducer.__new__(OrbisObjdumpProducer)
    producer._run = Mock(return_value="")
    with pytest.raises(ValueError, match="no version"):
        producer._read_version()

    producer._run = Mock(return_value="unexpected output")
    with pytest.raises(ValueError, match="did not report"):
        producer._read_target(Path("fixture.elf"))

    producer.executable = Path("objdump")
    producer.timeout_seconds = 1.0
    producer.__dict__.pop("_run")
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            orbis.subprocess,
            "run",
            Mock(side_effect=TimeoutExpired(["objdump"], 1.0)),
        )
        with pytest.raises(TimeoutError, match="timed out"):
            producer._run([])

        monkeypatch.setattr(
            orbis.subprocess,
            "run",
            Mock(return_value=CompletedProcess(["objdump"], 2, stdout="", stderr="failed")),
        )
        with pytest.raises(RuntimeError, match=r"failed \(2\)"):
            producer._run([])


@pytest.mark.unit
def test_orbis_range_grouping_and_cached_report_validation(tmp_path: Path) -> None:
    symbols = (
        OrbisFunctionSymbol(0x10, 2, ".text", "A"),
        OrbisFunctionSymbol(0x20_000, 2, ".text", "B"),
    )
    assert OrbisObjdumpProducer._group_ranges(symbols) == ((0x10, 0x12), (0x20_000, 0x20_002))
    assert OrbisObjdumpProducer._load_cached(tmp_path / "missing.json", "key") is None

    cached = tmp_path / "cached.json"
    cached.write_text("not-json", encoding="utf-8")
    assert OrbisObjdumpProducer._load_cached(cached, "key") is None
    cached.write_text('{"schema_version": "old"}', encoding="utf-8")
    assert OrbisObjdumpProducer._load_cached(cached, "key") is None

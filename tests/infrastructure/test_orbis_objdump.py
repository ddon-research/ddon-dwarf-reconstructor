"""Tests for bounded, cached PS4 Orbis disassembly."""

import hashlib
import json
from pathlib import Path

import pytest

import ddon_dwarf_reconstructor.infrastructure.orbis_objdump as orbis
from ddon_dwarf_reconstructor.domain.models.disassembly import OrbisInstruction, OrbisReference
from ddon_dwarf_reconstructor.infrastructure.orbis_objdump import (
    OrbisFunctionSymbol,
    OrbisObjdumpProducer,
)
from ddon_dwarf_reconstructor.infrastructure.orbis_objdump_profiles import (
    LLVM_METADATA_FLAGS,
    LLVM_TARGET_PROFILE,
    LLVM_TARGET_TRIPLE,
)
from ddon_dwarf_reconstructor.infrastructure.orbis_objdump_workflow import (
    _relevant_relocation_ranges,
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
def test_relocation_projection_includes_instruction_and_referenced_addresses() -> None:
    selected = (OrbisFunctionSymbol(0x100, 4, ".text", "Thing::method()"),)
    instructions = {
        0x100: OrbisInstruction(
            address=0x100,
            raw_bytes="90",
            mnemonic="nop",
            operands="",
            references=(
                OrbisReference("data", address=0),
                OrbisReference("data", address=0x200),
            ),
        )
    }

    assert _relevant_relocation_ranges(selected, instructions) == (
        (0, 1),
        (0x100, 0x104),
        (0x200, 0x201),
    )


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

    def __init__(
        self,
        executable: Path,
        cache_root: Path,
        llvm_readobj_path: Path | None = None,
        llvm_objdump_path: Path | None = None,
    ) -> None:
        super().__init__(
            executable,
            cache_root=cache_root,
            llvm_readobj_path=llvm_readobj_path,
            llvm_objdump_path=llvm_objdump_path,
        )
        self.calls: list[tuple[str, ...]] = []
        self.llvm_calls: list[tuple[str, ...]] = []

    def _run(self, arguments: list[str]) -> str:
        self.calls.append(tuple(arguments))
        exact = {
            ("--version",): "GNU objdump (GNU Binutils) 2.22 (Orbis version 8.00.0.398 f8fc24e5)\n",
            ("--help",): "--dwarf[=rawline,=decodedline,=info]\n",
        }
        if tuple(arguments) in exact:
            return exact[tuple(arguments)]
        responses = {
            "-f": "fixture: file format elf64-x86-64-freebsd\n",
            "-t": SYMBOLS,
            "-EL": DISASSEMBLY,
            "-p": "private headers\n",
            "-r": "",
        }
        if arguments[0] in responses:
            return responses[arguments[0]]
        if arguments[0] == "-R":
            raise RuntimeError("Invalid operation")
        if arguments[0] == "-g" or arguments[0].startswith("--dwarf="):
            return ""
        raise AssertionError(arguments)

    def _run_with_executable(self, executable: Path, arguments: list[str]) -> str:
        if self.llvm_readobj_path is not None and executable == self.llvm_readobj_path:
            self.llvm_calls.append(tuple(arguments))
            output = (
                '{"DynamicSection": [{"Tag": 1627390017}], '
                '"Relocations": [], "Dynamic Relocations": []}'
            )
            self._last_capture = (output, "", 0)
            return output
        if self.llvm_objdump_path is not None and executable == self.llvm_objdump_path:
            self.llvm_calls.append(tuple(arguments))
            if arguments == ["--version"]:
                output = "LLVM version 22.1.8\n"
            elif arguments == ["--help"]:
                output = (
                    "OVERVIEW: llvm object tool\n"
                    "  --triple=<value>\n"
                    "  -d\n  -l\n  -C\n"
                    "  --symbolize-operands\n"
                    "  --start-address=<address>\n"
                    "  --stop-address=<address>\n"
                )
            elif arguments and arguments[0].startswith("--triple="):
                output = DISASSEMBLY
            else:
                raise AssertionError(arguments)
            self._last_capture = (output, "", 0)
            return output
        return super()._run_with_executable(executable, arguments)


class UnsupportedTargetStub(StubOrbisProducer):
    """Expose an LLVM executable whose help surface lacks target selection."""

    def _run_with_executable(self, executable: Path, arguments: list[str]) -> str:
        if (
            self.llvm_objdump_path is not None
            and executable == self.llvm_objdump_path
            and arguments == ["--help"]
        ):
            self.llvm_calls.append(tuple(arguments))
            self._last_capture = ("llvm object tool\n", "", 0)
            return self._last_capture[0]
        return super()._run_with_executable(executable, arguments)


class IncompleteTargetStub(StubOrbisProducer):
    """Expose only triple selection, without the bounded-slice flags."""

    def _run_with_executable(self, executable: Path, arguments: list[str]) -> str:
        if (
            self.llvm_objdump_path is not None
            and executable == self.llvm_objdump_path
            and arguments == ["--help"]
        ):
            self.llvm_calls.append(tuple(arguments))
            self._last_capture = ("llvm object tool\n  --triple=<value>\n", "", 0)
            return self._last_capture[0]
        return super()._run_with_executable(executable, arguments)


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

    _assert_cache_pair(first, second, cold, warm)
    invocation_status = {item.profile: item.status for item in first.invocations}
    _assert_profile_statuses(invocation_status)
    assert not any(call[0] in {"-t", "-EL"} for call in warm.calls)


@pytest.mark.unit
def test_llvm_cross_check_retains_exact_external_command(tmp_path: Path) -> None:
    executable = tmp_path / "orbis-objdump.exe"
    executable.write_bytes(b"orbis tool fixture")
    llvm = tmp_path / "llvm-readobj.exe"
    llvm.write_bytes(b"llvm tool fixture")
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"orbis elf fixture")
    producer = StubOrbisProducer(executable, tmp_path / "cache", llvm)

    report = producer.produce(elf_path, "rLayout")

    invocation = next(
        item for item in report.invocations if item.profile == "llvm-elf-metadata-json"
    )
    assert invocation.command == (str(llvm), *LLVM_METADATA_FLAGS, str(elf_path))
    assert invocation.flags == (*LLVM_METADATA_FLAGS, str(elf_path))
    assert report.llvm_cross_check is not None
    assert report.llvm_cross_check.unknown_dynamic_tags == (1627390017,)
    assert producer.llvm_calls[-1:] == [tuple(invocation.flags)]


@pytest.mark.unit
def test_targeted_llvm_cross_check_uses_ps4_triple_and_range_slices(tmp_path: Path) -> None:
    executable = tmp_path / "orbis-objdump.exe"
    executable.write_bytes(b"orbis tool fixture")
    llvm = tmp_path / "llvm-objdump.exe"
    llvm.write_bytes(b"llvm objdump fixture")
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"orbis elf fixture")
    producer = StubOrbisProducer(executable, tmp_path / "cache", llvm_objdump_path=llvm)

    report = producer.produce(elf_path, "rLayout")

    assert report.llvm_targeted_cross_check is not None
    assert report.llvm_targeted_cross_check.profile == LLVM_TARGET_PROFILE
    assert report.llvm_targeted_cross_check.requested_triple == LLVM_TARGET_TRIPLE
    assert report.llvm_targeted_cross_check.status == "observed"
    assert report.llvm_targeted_cross_check.matched_instruction_count == 4
    target_calls = [
        call for call in producer.llvm_calls if call and call[0].startswith("--triple=")
    ]
    assert len(target_calls) == 2
    assert all(call[0] == f"--triple={LLVM_TARGET_TRIPLE}" for call in target_calls)
    assert target_calls[0][-3:-1] == ("--start-address=0x693e60", "--stop-address=0x694ae5")
    assert target_calls[0][-1] == str(elf_path)
    target_invocations = [
        item for item in report.invocations if item.profile == LLVM_TARGET_PROFILE
    ]
    assert len(target_invocations) == 2
    assert target_invocations[0].requested_triple == LLVM_TARGET_TRIPLE
    assert target_invocations[0].range_start == 0x693E60
    assert target_invocations[0].range_end == 0x694AE5


@pytest.mark.unit
def test_target_profile_changes_the_source_bound_artifact_key(tmp_path: Path) -> None:
    tool = orbis.OrbisToolIdentity("tool-sha", "orbis", "elf64-x86-64-freebsd")
    default_key = OrbisObjdumpProducer._artifact_key(
        "elf-sha", tool, "rLayout", llvm_target_triple=LLVM_TARGET_TRIPLE
    )
    alternate_key = OrbisObjdumpProducer._artifact_key(
        "elf-sha", tool, "rLayout", llvm_target_triple="x86_64-pc-freebsd"
    )

    assert default_key != alternate_key


@pytest.mark.unit
def test_targeted_llvm_profile_retains_unsupported_capability_status(tmp_path: Path) -> None:
    executable = tmp_path / "orbis-objdump.exe"
    executable.write_bytes(b"orbis tool fixture")
    llvm = tmp_path / "llvm-objdump.exe"
    llvm.write_bytes(b"llvm objdump fixture")
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"orbis elf fixture")

    report = UnsupportedTargetStub(
        executable,
        tmp_path / "cache",
        llvm_objdump_path=llvm,
    ).produce(elf_path, "rLayout")

    assert report.llvm_targeted_cross_check is not None
    assert report.llvm_targeted_cross_check.status == "unsupported"
    capability = next(
        item for item in report.invocations if item.profile == "llvm-objdump-capability"
    )
    assert capability.status == "unsupported"
    assert capability.target_status == "unsupported"


@pytest.mark.unit
def test_targeted_llvm_profile_rejects_unadvertised_slice_flags(tmp_path: Path) -> None:
    executable = tmp_path / "orbis-objdump.exe"
    executable.write_bytes(b"orbis tool fixture")
    llvm = tmp_path / "llvm-objdump.exe"
    llvm.write_bytes(b"llvm objdump fixture")
    elf_path = tmp_path / "DDOORBIS.elf"
    elf_path.write_bytes(b"orbis elf fixture")

    report = IncompleteTargetStub(
        executable,
        tmp_path / "cache",
        llvm_objdump_path=llvm,
    ).produce(elf_path, "rLayout")

    assert report.llvm_targeted_cross_check is not None
    assert report.llvm_targeted_cross_check.status == "unsupported"
    assert "--symbolize-operands" in report.llvm_targeted_cross_check.diagnostics[0]
    assert not any(
        invocation.command and invocation.command[1].startswith("--triple=")
        for invocation in report.invocations
        if invocation.profile == LLVM_TARGET_PROFILE
    )


def _assert_cache_pair(
    first: object, second: object, cold: StubOrbisProducer, warm: StubOrbisProducer
) -> None:
    assert first == second
    assert cold.last_cache_hit is False
    assert warm.last_cache_hit is True
    assert sum(1 for call in cold.calls if call[0] == "-t") == 1
    assert sum(1 for call in cold.calls if call[0] == "-EL") == 1
    assert any(call[0] == "-r" for call in cold.calls)
    assert not any(call[0] in {"-R", "-p", "-g"} for call in cold.calls)
    assert not any(call[0].startswith("--dwarf=") for call in cold.calls)


def _assert_profile_statuses(statuses: dict[str, str]) -> None:
    assert statuses["standard-relocations"] == "empty"
    assert "dynamic-relocations" not in statuses
    assert "private-headers" not in statuses


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
def test_instruction_parser_keeps_file_offsets_discriminators_and_reference_kinds() -> None:
    output = "\n".join(
        [
            "D:\\build\\rLayout.cpp:176 (discriminator 3)",
            "0000000000001000 <rLayout::load()> (File Offset: 0x2000) e8 01 00 00 00 callq 0000000000001006 <MtStream::read()> (File Offset: 0x2006)",
            "0000000000001005 <rLayout::load()+0x5> (File Offset: 0x2005) ff 15 00 00 00 00 callq *0x0(%rip) # 0000000000002000 <rLayout::DTI>",
        ]
    )

    instructions = OrbisObjdumpProducer.parse_instructions(output)

    assert instructions[0].file_offset == 0x2000
    assert instructions[0].source_discriminator == 3
    assert instructions[0].references[0].kind == "direct_call"
    assert instructions[0].references[0].resolved_name == "MtStream::read()"
    assert instructions[1].references[0].kind == "indirect_call"
    assert instructions[1].references[0].resolved_name == "rLayout::DTI"


@pytest.mark.unit
def test_instruction_parser_does_not_promote_immediates_to_data_references() -> None:
    output = "\n".join(
        [
            "0000000000001000 <rLayout::load()> (File Offset: 0x2000) be 10 02 00 00 mov $0x210,%esi",
            "0000000000001005 <rLayout::load()+0x5> (File Offset: 0x2005) 41 8b 4e 34 mov 0x34(%r14),%ecx",
            "0000000000001008 <rLayout::load()+0x8> (File Offset: 0x2008) ff 53 48 callq *0x48(%rbx)",
            "000000000000100b <rLayout::load()+0xb> (File Offset: 0x200b) e8 01 00 00 00 callq 0000000000001011",
        ]
    )

    instructions = OrbisObjdumpProducer.parse_instructions(output)

    assert instructions[0].references == ()
    assert instructions[1].references[0].address is None
    assert instructions[1].references[0].resolution_status == "unresolved"
    assert instructions[2].references[0].kind == "indirect_call"
    assert instructions[2].references[0].address is None
    assert instructions[2].references[0].resolution_status == "unresolved"
    assert instructions[3].references[0].kind == "direct_call"
    assert instructions[3].references[0].address == 0x1011
    assert instructions[3].references[0].resolution_status == "resolved"


@pytest.mark.unit
def test_relocation_parser_preserves_raw_rows_and_resolution_status() -> None:
    references = OrbisObjdumpProducer.parse_relocations(
        "RELOCATION RECORDS FOR [.text]:\n"
        "0000000000001000 R_X86_64_PC32 rLayout::DTI\n"
        "0000000000001008 R_X86_64_PC32 *UND*\n"
    )

    assert references[0].kind == "relocation"
    assert references[0].resolved_name == "rLayout::DTI"
    assert references[1].resolution_status == "unresolved"


@pytest.mark.unit
def test_llvm_json_parser_preserves_unknown_sce_dynamic_tags() -> None:
    output = '{"DynamicSection": [{"Tag": 1627390017}, {"Tag": 1627389999}]}'

    assert OrbisObjdumpProducer.parse_llvm_unknown_dynamic_tags(output) == (1627390017,)


@pytest.mark.unit
def test_llvm_json_parser_preserves_tags_before_unsupported_trailer() -> None:
    output = '{"DynamicSection": [{"Tag": 1627390017}]}Dynamic Relocations {}'

    tags, diagnostics = OrbisObjdumpProducer.parse_llvm_metadata(output)

    assert tags == (1627390017,)
    assert diagnostics and "trailing non-JSON" in diagnostics[0]


@pytest.mark.unit
def test_llvm_json_parser_repairs_orbis_unsupported_dynamic_relocation_trailer() -> None:
    output = '[{"DynamicSection":[{"Tag":1627390017}],"Relocations":[]Dynamic Relocations {}\n}]'

    tags, diagnostics = OrbisObjdumpProducer.parse_llvm_metadata(output)

    assert tags == (1627390017,)
    assert diagnostics and "Dynamic Relocations" in diagnostics[0]


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


@pytest.mark.unit
def test_profile_cache_rejects_changed_command_or_capture(tmp_path: Path) -> None:
    metadata = tmp_path / "profile.json"
    stdout_path = tmp_path / "profile.stdout.txt"
    stderr_path = tmp_path / "profile.stderr.txt"
    stdout_path.write_text("captured\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    tool = orbis.OrbisToolIdentity("tool-sha", "version", "target")
    metadata.write_text(
        json.dumps(
            {
                "profile": "symbols",
                "command": ["objdump", "-t", "fixture.elf"],
                "flags": ["-t", "fixture.elf"],
                "return_status": 0,
                "status": "observed",
                "stdout_sha256": "bad",
                "stderr_sha256": hashlib.sha256(b"").hexdigest(),
                "duration_ms": 1.0,
                "tool_identity": {
                    "executable_sha256": "tool-sha",
                    "version": "version",
                    "target": "target",
                },
            }
        ),
        encoding="utf-8",
    )

    assert (
        OrbisObjdumpProducer._load_profile_cache(
            metadata,
            stdout_path,
            stderr_path,
            "symbols",
            ["-t", "fixture.elf"],
            tool,
            Path("objdump"),
        )
        is None
    )

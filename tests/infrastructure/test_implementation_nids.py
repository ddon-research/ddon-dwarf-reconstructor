"""NID mapping, provenance, and fail-closed context evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.models.disassembly import (
    OrbisDynamicTag,
    OrbisRelocationEntry,
)
from ddon_dwarf_reconstructor.domain.models.implementation_validation import (
    NidResolution,
    ValidationStatus,
)
from ddon_dwarf_reconstructor.infrastructure.implementation_nids import nid_bindings

_NID_SUFFIX = "518D64A635DED8C1E6B039B1C3E55230"
_NID = "hcuQgD53UxM"
_MULTI_CHAR_NID = "f7uOxY9mM1U"


def _entry(symbol: str) -> OrbisRelocationEntry:
    return OrbisRelocationEntry(
        "jmprel-0",
        "jmprel",
        0,
        0x10,
        0,
        0,
        2,
        7,
        "R_X86_64_JUMP_SLOT",
        symbol,
        "",
        "",
        (),
    )


def _tags() -> tuple[OrbisDynamicTag, ...]:
    return (
        OrbisDynamicTag(0x61000015, "DT_SCE_IMPORT_LIB", (1 << 48) | 1),
        OrbisDynamicTag(0x61000016, "DT_SCE_NEEDED_MODULE", (2 << 48) | 2),
    )


def _provenance(database: Path, *, suffix: str = _NID_SUFFIX) -> dict[str, str]:
    return {
        "authority": "community_reference",
        "source_url": (
            "https://github.com/SocraticBliss/ps4_module_loader/blob/"
            "0123456789abcdef0123456789abcdef01234567/aerolib.csv"
        ),
        "source_commit": "0123456789abcdef0123456789abcdef01234567",
        "file_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "nid_suffix_hex": suffix,
    }


@pytest.mark.unit
@pytest.mark.functional
def test_community_csv_is_a_candidate_without_pinned_verification(tmp_path: Path) -> None:
    database = tmp_path / "aerolib.csv"
    database.write_text(f"{_NID} printf\n", encoding="utf-8")

    binding = nid_bindings(
        (_entry(f"{_NID}#B#C"),),
        _tags(),
        database=database,
    )[0]

    assert binding.resolved_name == "printf"
    assert binding.status is ValidationStatus.PARTIAL
    assert binding.resolution is NidResolution.COMMUNITY_CANDIDATE
    assert binding.hash_status is ValidationStatus.NOT_OBSERVED
    assert binding.context_status is ValidationStatus.OBSERVED
    assert "authority=community_reference" in (binding.source or "")


@pytest.mark.unit
@pytest.mark.functional
def test_pinned_community_mapping_verifies_hash_and_context(tmp_path: Path) -> None:
    database = tmp_path / "aerolib.csv"
    database.write_text(f"{_NID} printf\n", encoding="utf-8")
    manifest = tmp_path / "aerolib.provenance.json"
    manifest.write_text(json.dumps(_provenance(database)), encoding="utf-8")

    binding = nid_bindings(
        (_entry(f"{_NID}#B#C"),),
        _tags(),
        database=database,
        database_provenance=manifest,
    )[0]

    assert binding.status is ValidationStatus.OBSERVED
    assert binding.resolution is NidResolution.COMMUNITY_VERIFIED
    assert binding.hash_status is ValidationStatus.OBSERVED
    assert binding.context_status is ValidationStatus.OBSERVED
    assert binding.encoded_library_index == 1
    assert binding.encoded_module_index == 2
    assert "source_commit=" in (binding.source or "")
    assert "provenance_sha256=" in (binding.source or "")


@pytest.mark.unit
@pytest.mark.functional
def test_multi_character_context_uses_dynamic_table_ids(tmp_path: Path) -> None:
    database = tmp_path / "aerolib.csv"
    database.write_text(f"{_MULTI_CHAR_NID} __stack_chk_guard\n", encoding="utf-8")
    manifest = tmp_path / "aerolib.provenance.json"
    manifest.write_text(json.dumps(_provenance(database)), encoding="utf-8")
    tags = (
        OrbisDynamicTag(0x61000015, "DT_SCE_IMPORT_LIB", (76 << 48) | 1),
        OrbisDynamicTag(0x6100000F, "DT_SCE_NEEDED_MODULE", (36 << 48) | 2),
    )

    binding = nid_bindings(
        (_entry(f"{_MULTI_CHAR_NID}#BM#k"),),
        tags,
        database=database,
        database_provenance=manifest,
    )[0]

    assert binding.resolution is NidResolution.COMMUNITY_VERIFIED
    assert binding.status is ValidationStatus.OBSERVED
    assert binding.encoded_library_index == 76
    assert binding.encoded_module_index == 36
    assert binding.hash_status is ValidationStatus.OBSERVED
    assert binding.context_status is ValidationStatus.OBSERVED


@pytest.mark.unit
@pytest.mark.functional
def test_pinned_community_hash_or_context_mismatch_is_not_promoted(tmp_path: Path) -> None:
    database = tmp_path / "aerolib.csv"
    database.write_text(f"{_NID} printf\n", encoding="utf-8")
    manifest = tmp_path / "aerolib.provenance.json"
    manifest.write_text(json.dumps(_provenance(database)), encoding="utf-8")

    hash_database = tmp_path / "wrong-name.csv"
    hash_database.write_text(f"{_NID} not_printf\n", encoding="utf-8")
    hash_manifest = tmp_path / "wrong-name.provenance.json"
    hash_manifest.write_text(json.dumps(_provenance(hash_database)), encoding="utf-8")
    hash_mismatch = nid_bindings(
        (_entry(f"{_NID}#B#C"),),
        _tags(),
        database=hash_database,
        database_provenance=hash_manifest,
    )[0]
    context_mismatch = nid_bindings(
        (_entry(f"{_NID}#B#D"),),
        _tags(),
        database=database,
        database_provenance=manifest,
    )[0]

    assert hash_mismatch.status is ValidationStatus.FAILED
    assert hash_mismatch.resolution is NidResolution.CONFLICTING
    assert hash_mismatch.hash_status is ValidationStatus.FAILED
    assert context_mismatch.status is ValidationStatus.FAILED
    assert context_mismatch.resolution is NidResolution.CONFLICTING
    assert context_mismatch.context_status is ValidationStatus.FAILED


@pytest.mark.unit
@pytest.mark.functional
def test_provenance_digest_and_duplicate_names_fail_closed(tmp_path: Path) -> None:
    database = tmp_path / "aerolib.csv"
    database.write_text(f"{_NID} printf\n", encoding="utf-8")
    wrong_manifest = tmp_path / "wrong.json"
    wrong_manifest.write_text(
        json.dumps({**_provenance(database), "file_sha256": "0" * 64}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="SHA-256"):
        nid_bindings((), (), database=database, database_provenance=wrong_manifest)

    conflicting = tmp_path / "conflicting.txt"
    conflicting.write_text(
        f"{_NID} printf\n{_NID} puts\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="conflicting names"):
        nid_bindings((), (), database=conflicting)

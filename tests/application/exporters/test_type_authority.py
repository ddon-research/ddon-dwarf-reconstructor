"""Golden build-scoped type-authority contract tests."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.application.exporters import get_type_authority
from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo, MemberInfo


def _golden_rlayout() -> ClassInfo:
    return ClassInfo(
        name="rLayout",
        byte_size=528,
        members=[
            MemberInfo("DTI", "MyDTI", 0x117EC472, is_static=True),
            MemberInfo("mpArray", "SetInfo*", 0x117EC4ED, 112),
            MemberInfo("mArrayNum", "u32", offset=120),
            MemberInfo("mIndex", "unsigned char[256]", offset=124),
            MemberInfo("mSetInfoNeedNums", "unsigned int[22]", offset=380),
            MemberInfo("mpSetInfoBuffer", "void*", offset=472),
            MemberInfo("mSetInfoSingleNewArray", "MtArray", offset=480),
            MemberInfo("mLotType", "TYPE", offset=512),
            MemberInfo("mLayoutID", "stLayoutID", offset=516),
            MemberInfo("mSplitID", "stSplitID", offset=520),
        ],
        methods=[],
        base_classes=["cResource"],
        enums=[],
        nested_structs=[],
        unions=[],
        declaration_file="rLayout.h",
        declaration_line=40,
        die_offset=0x117EC452,
        cu_offset=0x117EBF8B,
    )


@pytest.mark.unit
def test_ps4_rlayout_authority_pins_layout_mydti_and_alternative() -> None:
    authority = get_type_authority("ps4-02020005", "rLayout")

    assert authority is not None
    authority.validate_class_info(_golden_rlayout())
    manifest = authority.to_manifest()
    assert manifest["die_offset_hex"] == "0x117ec452"
    assert manifest["cu_offset_hex"] == "0x117ebf8b"
    assert manifest["rejected_candidates"] == [
        {
            "die_offset": 0x76133,
            "die_offset_hex": "0x76133",
            "reason": "lower-completeness duplicate with one nested enum and one nested structure",
        }
    ]
    assert any("direct DIE identity" in basis for basis in manifest["selection_basis"])
    assert not any("DW_AT_containing_type" in basis for basis in manifest["selection_basis"])
    assert any(
        member.name == "DTI" and member.type_offset == 0x117EC472 for member in authority.members
    )


@pytest.mark.unit
def test_ps4_rlayout_authority_rejects_cached_duplicate() -> None:
    authority = get_type_authority("ps4-02020005", "rLayout")
    assert authority is not None
    duplicate = _golden_rlayout()
    duplicate.die_offset = 0x76133

    with pytest.raises(ValueError, match="die_offset 483635"):
        authority.validate_class_info(duplicate)


@pytest.mark.unit
def test_ps4_rlayout_authority_validates_die_identity() -> None:
    authority = get_type_authority("ps4-02020005", "rLayout")
    assert authority is not None
    die = Mock()
    die.offset = 0x117EC452
    die.tag = "DW_TAG_class_type"
    die.attributes = {"DW_AT_name": Mock(value=b"rLayout")}

    authority.validate_die(die)


@pytest.mark.unit
def test_ps4_rwarp_location_authority_pins_generic_second_root() -> None:
    authority = get_type_authority("ps4-02020005", "rWarpLocation")

    assert authority is not None
    assert authority.die_offset == 0x1C5758E
    assert authority.cu_offset == 0x1B6B20A
    assert authority.byte_size == 128
    assert authority.base_class == "rTbl2<cWarpLocation>"
    assert authority.members[0].name == "DTI"
    assert authority.members[0].type_offset == 0x1C575B0
    assert authority.members[0].is_static
    assert len(authority.rejected_candidates) == 6
    assert all("equivalent" in reason for _offset, reason in authority.rejected_candidates)

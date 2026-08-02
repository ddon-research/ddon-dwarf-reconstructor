"""Build-scoped authority contracts for ambiguous DWARF root symbols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from elftools.dwarf.die import DIE

from ...domain.models.dwarf import ClassInfo


@dataclass(frozen=True)
class MemberAuthority:
    """One layout fact required by an approved root definition."""

    name: str
    type_name: str
    offset: int | None
    type_offset: int | None = None
    is_static: bool = False


@dataclass(frozen=True)
class TypeAuthority:
    """An explicit, evidence-backed choice among duplicate DWARF definitions."""

    build_id: str
    symbol: str
    die_offset: int
    cu_offset: int
    tag: str
    byte_size: int
    declaration_file: str
    declaration_line: int
    base_class: str
    members: tuple[MemberAuthority, ...]
    selection_basis: tuple[str, ...]
    rejected_candidates: tuple[tuple[int, str], ...]

    def validate_die(self, die: DIE) -> None:
        """Fail when direct offset resolution does not produce the approved DIE."""
        name_attribute = die.attributes.get("DW_AT_name")
        raw_name = name_attribute.value if name_attribute is not None else None
        actual_name = (
            raw_name.decode("utf-8", errors="replace") if isinstance(raw_name, bytes) else raw_name
        )
        errors: list[str] = []
        if die.offset != self.die_offset:
            errors.append(f"DIE offset 0x{die.offset:x} != 0x{self.die_offset:x}")
        if die.tag != self.tag:
            errors.append(f"tag {die.tag!r} != {self.tag!r}")
        if actual_name != self.symbol:
            errors.append(f"name {actual_name!r} != {self.symbol!r}")
        if errors:
            raise ValueError(
                f"Authority contract failed for {self.build_id}/{self.symbol}: " + "; ".join(errors)
            )

    def validate_class_info(self, class_info: ClassInfo) -> None:
        """Validate exported layout facts against the approved golden contract."""
        errors = self._scalar_validation_errors(class_info)
        if self.base_class not in class_info.base_classes:
            errors.append(f"missing base class {self.base_class!r}")
        errors.extend(self._member_validation_errors(class_info))
        if errors:
            raise ValueError(
                f"Authority contract failed for {self.build_id}/{self.symbol}: " + "; ".join(errors)
            )

    def _scalar_validation_errors(self, class_info: ClassInfo) -> list[str]:
        errors: list[str] = []
        expected_scalars = {
            "name": self.symbol,
            "die_offset": self.die_offset,
            "cu_offset": self.cu_offset,
            "byte_size": self.byte_size,
            "declaration_file": self.declaration_file,
            "declaration_line": self.declaration_line,
        }
        for attribute, expected in expected_scalars.items():
            actual = getattr(class_info, attribute)
            if actual != expected:
                errors.append(f"{attribute} {actual!r} != {expected!r}")
        return errors

    def _member_validation_errors(self, class_info: ClassInfo) -> list[str]:
        errors: list[str] = []
        actual_members = {member.name: member for member in class_info.members}
        for expected in self.members:
            actual = actual_members.get(expected.name)
            if actual is None:
                errors.append(f"missing member {expected.name!r}")
                continue
            for attribute in ("type_name", "offset", "type_offset", "is_static"):
                expected_value = getattr(expected, attribute)
                if expected_value is not None and getattr(actual, attribute) != expected_value:
                    errors.append(
                        f"member {expected.name}.{attribute} "
                        f"{getattr(actual, attribute)!r} != {expected_value!r}"
                    )
        return errors

    def to_manifest(self) -> dict[str, Any]:
        """Return a stable manifest representation of the selection decision."""
        return {
            "build_id": self.build_id,
            "symbol": self.symbol,
            "die_offset": self.die_offset,
            "die_offset_hex": f"0x{self.die_offset:x}",
            "cu_offset": self.cu_offset,
            "cu_offset_hex": f"0x{self.cu_offset:x}",
            "tag": self.tag,
            "selection_basis": list(self.selection_basis),
            "rejected_candidates": [
                {"die_offset": offset, "die_offset_hex": f"0x{offset:x}", "reason": reason}
                for offset, reason in self.rejected_candidates
            ],
        }


_RLAYOUT_02020005 = TypeAuthority(
    build_id="ps4-02020005",
    symbol="rLayout",
    die_offset=0x117EC452,
    cu_offset=0x117EBF8B,
    tag="DW_TAG_class_type",
    byte_size=528,
    declaration_file="rLayout.h",
    declaration_line=40,
    base_class="cResource",
    members=(
        MemberAuthority("DTI", "MyDTI", None, 0x117EC472, True),
        MemberAuthority("mpArray", "SetInfo*", 112, 0x117EC4ED),
        MemberAuthority("mArrayNum", "u32", 120),
        MemberAuthority("mIndex", "unsigned char[256]", 124),
        MemberAuthority("mSetInfoNeedNums", "unsigned int[22]", 380),
        MemberAuthority("mpSetInfoBuffer", "void*", 472),
        MemberAuthority("mSetInfoSingleNewArray", "MtArray", 480),
        MemberAuthority("mLotType", "TYPE", 512),
        MemberAuthority("mLayoutID", "stLayoutID", 516),
        MemberAuthority("mSplitID", "stSplitID", 520),
    ),
    selection_basis=(
        "class definition named rLayout declared by rLayout.h",
        "direct DW_TAG_inheritance resolves to cResource",
        "DW_AT_containing_type references identify this class definition",
        "static DTI member references nearby MyDTI DIE 0x117ec472",
        "candidate has two nested enums and one nested structure",
    ),
    rejected_candidates=(
        (0x76133, "lower-completeness duplicate with one nested enum and one nested structure"),
    ),
)

_RWARPLOCATION_02020005 = TypeAuthority(
    build_id="ps4-02020005",
    symbol="rWarpLocation",
    die_offset=0x1C5758E,
    cu_offset=0x1B6B20A,
    tag="DW_TAG_class_type",
    byte_size=128,
    declaration_file="rWarpLocation.h",
    declaration_line=55,
    base_class="rTbl2<cWarpLocation>",
    members=(MemberAuthority("DTI", "MyDTI", None, 0x1C575B0, True),),
    selection_basis=(
        "complete class definition named rWarpLocation declared by rWarpLocation.h",
        "direct DW_TAG_inheritance resolves to rTbl2<cWarpLocation>",
        "static DTI member references nearby MyDTI DIE 0x1c575b0",
        "equal-scoring complete definitions have the same indexed structural fingerprint",
        "canonical score-descending CU-ascending DIE-ascending ordering",
    ),
    rejected_candidates=(
        (0x9D7E545, "equivalent complete definition; later CU/DIE tie-break"),
        (0xD9237F5, "equivalent complete definition; later CU/DIE tie-break"),
        (0x12575B2F, "equivalent complete definition; later CU/DIE tie-break"),
        (0x139C8216, "equivalent complete definition; later CU/DIE tie-break"),
        (0x1D5AB5C7, "equivalent complete definition; later CU/DIE tie-break"),
        (0x1F4F6C48, "equivalent complete definition; later CU/DIE tie-break"),
    ),
)

_AUTHORITIES = {
    (_RLAYOUT_02020005.build_id, _RLAYOUT_02020005.symbol): _RLAYOUT_02020005,
    (_RWARPLOCATION_02020005.build_id, _RWARPLOCATION_02020005.symbol): (_RWARPLOCATION_02020005),
}


def get_type_authority(build_id: str, symbol: str) -> TypeAuthority | None:
    """Return the approved contract for a build/symbol pair, if one exists."""
    return _AUTHORITIES.get((build_id, symbol))

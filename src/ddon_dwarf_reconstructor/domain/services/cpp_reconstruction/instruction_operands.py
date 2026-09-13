"""Shared operand normalization for conservative instruction-effect analysis."""

from __future__ import annotations

import re

from ...models.disassembly import OrbisInstruction

_REGISTER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])%?(?:r(?:[89]|1[0-5])(?:[bwd])?|"
    r"r(?:[abcd]x|[sb]p|[sd]i|ip)|"
    r"e?[abcd]x|e?[sb]p|e?[sd]i|[abcd][lh]|sil|dil|spl|bpl|"
    r"xmm\d+|ymm\d+|zmm\d+)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_IMMEDIATE_PATTERN = re.compile(r"(?:\$|#)?(?:-?0x[0-9a-f]+|-?\d+)$", re.IGNORECASE)
_CALLEE_SAVED = frozenset({"rbx", "rbp", "r12", "r13", "r14", "r15"})
_MNEMONIC_ALIASES = {
    "movslq": "movsxd",
    "movswl": "movsx",
    "movzwl": "movzx",
    "movzbl": "movzx",
    "movzbq": "movzx",
    "movzwq": "movzx",
    "movsbq": "movsx",
    "movswq": "movsx",
}
_CONDITIONAL_BRANCHES = frozenset(
    [
        "ja",
        "jae",
        "jb",
        "jbe",
        "jc",
        "je",
        "jg",
        "jge",
        "jl",
        "jle",
        "jna",
        "jnae",
        "jnb",
        "jnbe",
        "jnc",
        "jne",
        "jng",
        "jnge",
        "jnl",
        "jnle",
        "jno",
        "jnp",
        "jns",
        "jnz",
        "jo",
        "jp",
        "jpe",
        "jpo",
        "js",
        "jz",
        "jecxz",
        "jrcxz",
        "jcxz",
        "loop",
        "loope",
        "loopne",
        "loopnz",
        "loopz",
    ]
)
_FLAG_WRITERS = frozenset({"add", "and", "cmp", "dec", "inc", "or", "sbb", "sub", "test", "xor"})
_KNOWN_MNEMONICS = (
    frozenset(
        [
            "adc",
            "add",
            "and",
            "call",
            "clc",
            "cld",
            "cmc",
            "cmp",
            "cqo",
            "cqto",
            "dec",
            "div",
            "idiv",
            "imul",
            "inc",
            "jmp",
            "lea",
            "leave",
            "mov",
            "movabs",
            "movdqa",
            "movdqu",
            "movaps",
            "movups",
            "movs",
            "movsx",
            "movsxd",
            "movzx",
            "mul",
            "neg",
            "nop",
            "not",
            "or",
            "pop",
            "push",
            "ret",
            "sal",
            "rol",
            "ror",
            "sar",
            "sbb",
            "seta",
            "setae",
            "setb",
            "setbe",
            "sete",
            "setg",
            "setge",
            "setl",
            "setle",
            "setne",
            "setno",
            "seto",
            "sets",
            "shl",
            "shr",
            "sub",
            "syscall",
            "test",
            "vzeroupper",
            "xor",
            "cmova",
            "cmovae",
            "cmovb",
            "cmovbe",
            "cmovc",
            "cmove",
            "cmovg",
            "cmovge",
            "cmovl",
            "cmovle",
            "cmovna",
            "cmovnae",
            "cmovnb",
            "cmovnbe",
            "cmovnc",
            "cmovne",
            "cmovng",
            "cmovnge",
            "cmovnl",
            "cmovnle",
            "cmovno",
            "cmovnp",
            "cmovns",
            "cmovnz",
            "cmovo",
            "cmovp",
            "cmovpe",
            "cmovpo",
            "cmovs",
            "cmovz",
            "vmovaps",
            "vmovss",
            "vxorps",
        ]
    )
    | _CONDITIONAL_BRANCHES
)
_REGISTER_WRITERS = frozenset(
    {
        "add",
        "and",
        "cmova",
        "cmovae",
        "cmovb",
        "cmovbe",
        "cmovc",
        "cmove",
        "cmovg",
        "cmovge",
        "cmovl",
        "cmovle",
        "cmovna",
        "cmovnae",
        "cmovnb",
        "cmovnbe",
        "cmovnc",
        "cmovne",
        "cmovng",
        "cmovnge",
        "cmovnl",
        "cmovnle",
        "cmovno",
        "cmovnp",
        "cmovns",
        "cmovnz",
        "cmovo",
        "cmovp",
        "cmovpe",
        "cmovpo",
        "cmovs",
        "cmovz",
        "cmp",
        "dec",
        "idiv",
        "imul",
        "inc",
        "lea",
        "mov",
        "movabs",
        "movs",
        "movsx",
        "movsxd",
        "movzx",
        "neg",
        "not",
        "or",
        "pop",
        "rol",
        "ror",
        "sar",
        "seta",
        "setae",
        "setb",
        "setbe",
        "sete",
        "setg",
        "setge",
        "setl",
        "setle",
        "setne",
        "setno",
        "seto",
        "sets",
        "shl",
        "shr",
        "sub",
        "vmovaps",
        "vmovss",
        "vxorps",
        "xor",
    }
)


def base_mnemonic(value: str) -> str:
    """Normalize AT&T prefixes, width suffixes, and common assembler aliases."""
    mnemonic = value.strip().lower().split(".", 1)[0] if value else ""
    prefixes = (
        "repnz",
        "repne",
        "repe",
        "repz",
        "rep",
        "lock",
        "data32",
        "data16",
        "addr32",
        "addr16",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if mnemonic == prefix:
                return "nop"
            if mnemonic.startswith(prefix + " "):
                mnemonic = mnemonic[len(prefix) :].lstrip()
                changed = True
                break
    mnemonic = _MNEMONIC_ALIASES.get(mnemonic, mnemonic)
    mnemonic = {"sal": "shl", "retn": "ret", "retq": "ret"}.get(mnemonic, mnemonic)
    if mnemonic.endswith(("q", "w", "l", "b")) and mnemonic[:-1] in _KNOWN_MNEMONICS:
        return mnemonic[:-1]
    return mnemonic


def canonical_register(value: str) -> str:
    """Normalize register width aliases to their 64-bit register family."""
    register = value.lower().lstrip("%")
    if re.fullmatch(r"r(?:[89]|1[0-5])[bwd]", register):
        register = register[:-1]
    aliases = {
        "eax": "rax",
        "ax": "rax",
        "al": "rax",
        "ah": "rax",
        "ebx": "rbx",
        "bx": "rbx",
        "bl": "rbx",
        "bh": "rbx",
        "ecx": "rcx",
        "cx": "rcx",
        "cl": "rcx",
        "ch": "rcx",
        "edx": "rdx",
        "dx": "rdx",
        "dl": "rdx",
        "dh": "rdx",
        "esp": "rsp",
        "sp": "rsp",
        "spl": "rsp",
        "ebp": "rbp",
        "bp": "rbp",
        "bpl": "rbp",
        "esi": "rsi",
        "si": "rsi",
        "sil": "rsi",
        "edi": "rdi",
        "di": "rdi",
        "dil": "rdi",
    }
    return aliases.get(register, register)


def has_memory_operand(operands: str) -> bool:
    return bool(re.search(r"\([^)]*\)|\[[^]]+\]", operands))


def writes_memory(mnemonic: str, operands: str) -> bool:
    if not has_memory_operand(operands) or mnemonic in {"cmp", "test", "lea"}:
        return False
    if mnemonic in {"push", "call"}:
        return True
    parts = [part.strip() for part in operands.split(",") if part.strip()]
    return bool(parts) and has_memory_operand(parts[-1])


def destination_register(operands: str) -> str | None:
    parts = [part.strip() for part in operands.split(",") if part.strip()]
    if not parts:
        return None
    match = _REGISTER_PATTERN.search(parts[-1])
    return canonical_register(match.group(0)) if match else None


def last_register(operands: str) -> str | None:
    matches = _REGISTER_PATTERN.findall(operands)
    return canonical_register(matches[-1]) if matches else None


def first_register(operands: str) -> str | None:
    matches = _REGISTER_PATTERN.findall(operands)
    return canonical_register(matches[0]) if matches else None


def destination_is(operands: str, register: str) -> bool:
    return destination_register(operands) == register


def frame_pointer_displacement(operands: str) -> int | None:
    match = re.search(
        r"(?P<disp>-?(?:0x[0-9a-f]+|\d+))?\([^)]*%rbp[^)]*\)", operands, re.IGNORECASE
    )
    if match is None:
        return None
    value = match.group("disp")
    if value is None:
        return 0
    try:
        return int(value, 0)
    except ValueError:
        return None


def mentions_stack_pointer(operands: str) -> bool:
    return any(canonical_register(item) == "rsp" for item in _REGISTER_PATTERN.findall(operands))


def stack_immediate(operands: str) -> int:
    for part in (item.strip() for item in operands.split(",")):
        candidate = part.removeprefix("$").removeprefix("#")
        if _IMMEDIATE_PATTERN.fullmatch(part) or _IMMEDIATE_PATTERN.fullmatch(candidate):
            try:
                value = int(candidate, 0)
                if candidate.lower().startswith("0x") and value >= 1 << 63:
                    value -= 1 << 64
                return value
            except ValueError:
                return 0
    return 0


def is_indirect_target(operands: str, instruction: OrbisInstruction) -> bool:
    if instruction.call_target_address is not None or instruction.call_target_name is not None:
        return False
    value = operands.strip().lstrip("*")
    return not bool(_IMMEDIATE_PATTERN.fullmatch(value))


__all__ = [
    "_CALLEE_SAVED",
    "_CONDITIONAL_BRANCHES",
    "_FLAG_WRITERS",
    "_KNOWN_MNEMONICS",
    "_REGISTER_PATTERN",
    "_REGISTER_WRITERS",
    "base_mnemonic",
    "canonical_register",
    "destination_is",
    "destination_register",
    "first_register",
    "frame_pointer_displacement",
    "has_memory_operand",
    "is_indirect_target",
    "last_register",
    "mentions_stack_pointer",
    "stack_immediate",
    "writes_memory",
]

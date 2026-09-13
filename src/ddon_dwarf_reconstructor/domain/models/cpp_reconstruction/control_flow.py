"""Published value objects for bounded C++ control-flow analysis."""

from __future__ import annotations

from dataclasses import dataclass

from ..implementation_validation import ValidationStatus


@dataclass(frozen=True, slots=True)
class ControlFlowStep:
    """Bounded effect summary for one instruction in a method CFG."""

    address: int
    branch_kind: str = "normal"
    target: int | None = None
    stack_delta: int = 0
    terminal: bool = False
    returns: bool = True
    uncertain: bool = False
    saved: frozenset[str] = frozenset()
    restored: frozenset[str] = frozenset()
    writes: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ControlFlowJoin:
    """Result of joining bounded conditional paths without guessing missing edges."""

    status: ValidationStatus
    stack_delta: int | None = None
    stack_min: int | None = None
    stack_max: int | None = None
    callee_saved_preserved: bool | None = None
    diagnostics: tuple[str, ...] = ()

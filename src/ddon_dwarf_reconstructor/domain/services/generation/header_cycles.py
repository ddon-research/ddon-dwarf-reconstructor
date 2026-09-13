"""Deterministic cycle analysis used by header dependency ordering."""

from __future__ import annotations

from collections.abc import Iterator


def strongly_connected_components(
    dependencies: dict[str, set[str]],
) -> tuple[tuple[str, ...], ...]:
    """Return non-trivial strongly connected components in stable order."""
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []
    next_index = 0

    for name in sorted(dependencies):
        if name in indices:
            continue
        indices[name] = next_index
        lowlinks[name] = next_index
        next_index += 1
        stack.append(name)
        on_stack.add(name)
        frames: list[tuple[str, Iterator[str]]] = [
            (name, iter(sorted(dependencies.get(name, ())))),
        ]
        while frames:
            current, edges = frames[-1]
            try:
                dependency = next(edges)
            except StopIteration:
                frames.pop()
                if frames:
                    parent = frames[-1][0]
                    lowlinks[parent] = min(lowlinks[parent], lowlinks[current])
                _finish_component(
                    current, dependencies, indices, lowlinks, stack, on_stack, components
                )
                continue
            if dependency not in indices:
                indices[dependency] = next_index
                lowlinks[dependency] = next_index
                next_index += 1
                stack.append(dependency)
                on_stack.add(dependency)
                frames.append((dependency, iter(sorted(dependencies.get(dependency, ())))))
            elif dependency in on_stack:
                lowlinks[current] = min(lowlinks[current], indices[dependency])
    return tuple(sorted(components))


def _finish_component(
    name: str,
    dependencies: dict[str, set[str]],
    indices: dict[str, int],
    lowlinks: dict[str, int],
    stack: list[str],
    on_stack: set[str],
    components: list[tuple[str, ...]],
) -> None:
    if lowlinks[name] != indices[name]:
        return
    component: list[str] = []
    while True:
        candidate = stack.pop()
        on_stack.remove(candidate)
        component.append(candidate)
        if candidate == name:
            break
    if len(component) > 1 or name in dependencies.get(name, set()):
        components.append(tuple(sorted(component)))


def cycle_fallback_name(remaining: dict[str, set[str]], preferred: list[str]) -> str:
    """Choose the first deterministic recovery node from a cyclic remainder."""
    return next((name for name in preferred if name in remaining), min(remaining))

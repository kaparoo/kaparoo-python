"""Read the values a `Literal` admits, through a PEP 695 alias or not."""

from __future__ import annotations

__all__ = ("literal_values",)

from typing import TYPE_CHECKING, Literal, TypeAliasType, get_args, get_origin

if TYPE_CHECKING:
    from typing import Any


def literal_values(alias: object) -> tuple[Any, ...]:
    """Return the values a `Literal` admits, resolving a PEP 695 alias first.

    A `type X = Literal[...]` alias is a `TypeAliasType`, which `get_args` does
    not see through (it returns an empty tuple). This follows `__value__` so the
    values are read either way, and refuses anything that is not a `Literal`
    rather than reporting it as empty.

    A PEP 695 alias evaluates its value lazily, so the module defining the alias
    must import `Literal` at runtime; a `TYPE_CHECKING`-only import raises
    `NameError` when `__value__` is first read here.

    Raises:
        TypeError: If `alias` does not resolve to a `Literal`.
    """
    target = alias
    while isinstance(target, TypeAliasType):
        target = target.__value__

    if get_origin(target) is not Literal:
        msg = f"expected a Literal, got {alias!r}"
        raise TypeError(msg)

    return get_args(target)

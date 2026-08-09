"""Resolve a name to an `Enum` member."""

from __future__ import annotations

__all__ = ("resolve_enum",)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection
    from enum import Enum


def resolve_enum[E: Enum](
    name: str,
    enum: type[E],
    *,
    exclude: Collection[E] = (),
    case_sensitive: bool = False,
) -> E:
    """Resolve `name` to a member of `enum` by member name.

    Lookup is case-insensitive unless `case_sensitive`. Members in `exclude`
    are rejected like unknown names and are never offered in the error message,
    which covers a sentinel member no caller may request.

    Raises:
        ValueError: If `name` names no selectable member of `enum`.
    """
    excluded = set(exclude)
    selectable = [member for member in enum if member not in excluded]
    lookup = {
        (member.name if case_sensitive else member.name.casefold()): member
        for member in selectable
    }

    resolved = lookup.get(name if case_sensitive else name.casefold())
    if resolved is None:
        names = sorted(member.name for member in selectable)
        msg = f"{enum.__name__} must be one of {names} (got {name!r})"
        raise ValueError(msg)

    return resolved

"""TypedDicts for forwarding the `search_*` keyword set."""

from __future__ import annotations

__all__ = ("SearchKwargs", "WalkKwargs")

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from kaparoo.filesystem.exclude import ExcludeRule
    from kaparoo.filters import Filter
    from kaparoo.filters.types import FilterDict


class WalkKwargs(TypedDict, total=False):
    """The `search_*` keyword set except `predicate`.

    A wrapper that owns its `predicate`, whether it supplies one internally or
    exposes one of a different type over the objects it returns, can accept and
    forward the rest as `**walk: Unpack[WalkKwargs]` without re-declaring each
    key. `stringify` is excluded too, since it selects the return type through
    overloads.
    """

    part_filter: Filter | FilterDict | None
    name_filter: Filter | FilterDict | None
    exclude: ExcludeRule | Iterable[ExcludeRule] | None
    descend: Callable[[Path], bool] | None
    min_depth: int
    max_depth: int | None
    ordered: bool


class SearchKwargs(WalkKwargs, total=False):
    """`WalkKwargs` plus `predicate`: the full forwardable `search_*` keyword set.

    A wrapper that forwards the walk verbatim uses this; one that owns its
    `predicate` forwards `WalkKwargs` and declares `predicate` itself.
    """

    predicate: Callable[[Path], bool] | None

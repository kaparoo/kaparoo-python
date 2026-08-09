"""The `SearchKwargs` TypedDict for forwarding the `search_*` keyword set."""

from __future__ import annotations

__all__ = ("SearchKwargs",)

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from kaparoo.filesystem.exclude import ExcludeRule
    from kaparoo.filters import Filter
    from kaparoo.filters.types import FilterDict


class SearchKwargs(TypedDict, total=False):
    """The keyword arguments `search_paths` / `search_files` / `search_dirs` share.

    A wrapper can accept and forward the whole set as
    `**options: Unpack[SearchKwargs]` without re-declaring each key. `stringify`
    is excluded, since it selects the return type through overloads.
    """

    part_filter: Filter | FilterDict | None
    name_filter: Filter | FilterDict | None
    predicate: Callable[[Path], bool] | None
    exclude: ExcludeRule | Iterable[ExcludeRule] | None
    descend: Callable[[Path], bool] | None
    min_depth: int
    max_depth: int | None
    ordered: bool

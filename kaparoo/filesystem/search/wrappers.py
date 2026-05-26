from __future__ import annotations

__all__ = ("search_dirs", "search_files", "search_paths")

from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.search.classes import DirSearch, FileSearch, PathSearch

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path
    from typing import Literal

    from kaparoo.filesystem.search.classes import _Filters
    from kaparoo.filesystem.types import StrPath


# Thin wrappers over the `Search` subclasses in `classes`. The classes are
# implementation details; users call these functions. Each wrapper
# repeats the full signature and overloads so the help / IDE experience
# reads as a plain function, not as a bound classmethod.


@overload
def search_paths(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def search_paths(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def search_paths(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def search_paths(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Walk `root` and return both directory and file paths that match."""
    return PathSearch.run(
        root,
        part_filter=part_filter,
        name_filter=name_filter,
        predicate=predicate,
        min_depth=min_depth,
        max_depth=max_depth,
        ordered=ordered,
        stringify=stringify,
    )


@overload
def search_files(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def search_files(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def search_files(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def search_files(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Walk `root` and return the file paths that match."""
    return FileSearch.run(
        root,
        part_filter=part_filter,
        name_filter=name_filter,
        predicate=predicate,
        min_depth=min_depth,
        max_depth=max_depth,
        ordered=ordered,
        stringify=stringify,
    )


@overload
def search_dirs(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def search_dirs(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def search_dirs(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def search_dirs(
    root: StrPath,
    *,
    part_filter: _Filters | None = None,
    name_filter: _Filters | None = None,
    predicate: Callable[[Path], bool] | None = None,
    min_depth: int = 1,
    max_depth: int | None = None,
    ordered: bool = True,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Walk `root` and return the directory paths that match."""
    return DirSearch.run(
        root,
        part_filter=part_filter,
        name_filter=name_filter,
        predicate=predicate,
        min_depth=min_depth,
        max_depth=max_depth,
        ordered=ordered,
        stringify=stringify,
    )

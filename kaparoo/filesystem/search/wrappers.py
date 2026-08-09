"""Public search entry points: `search_paths` / `search_files` / `search_dirs`."""

from __future__ import annotations

__all__ = ("search_dirs", "search_files", "search_paths")

from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.search.classes import DirSearch, FileSearch, PathSearch

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal, Unpack

    from kaparoo.filesystem.search.types import SearchKwargs
    from kaparoo.filesystem.types import StrPath


@overload
def search_paths(
    root: StrPath, *, stringify: Literal[False] = False, **options: Unpack[SearchKwargs]
) -> list[Path]: ...


@overload
def search_paths(
    root: StrPath, *, stringify: Literal[True], **options: Unpack[SearchKwargs]
) -> list[str]: ...


@overload
def search_paths(
    root: StrPath, *, stringify: bool, **options: Unpack[SearchKwargs]
) -> list[Path] | list[str]: ...


def search_paths(
    root: StrPath, *, stringify: bool = False, **options: Unpack[SearchKwargs]
) -> list[Path] | list[str]:
    """Walk `root` and return file and directory paths that match.

    Entries (files and sub-directories) are returned if they pass
    `part_filter` (on the visited directory's relative path), `name_filter`
    (on the entry's leaf name), `predicate` (on the entry's full `Path`), and
    lie within `[min_depth, max_depth]`.

    Keyword Args:
        part_filter: Filter on each visited directory's relative path
            string. Accepts a `Filter` or a `FilterDict`. None (default)
            accepts all directories.
        name_filter: Filter on each entry's leaf name. Accepts a `Filter`
            or a `FilterDict`. None (default) accepts all names.
        predicate: Callable on each entry's full `Path` for a final check.
            None (default) accepts all paths.
        exclude: Paths to skip: a `StrPath` (absolute under `root` or
            root-relative), a `Filter` (on the root-relative POSIX path), a
            `Callable` on the candidate `Path`, or an iterable of these
            (OR-combined). An excluded *directory* is pruned (its subtree is
            not descended). None (default) excludes nothing.
        descend: Callable on each sub-directory's full `Path` deciding whether
            to visit it. A directory that fails is still offered to the filters
            and may be returned, but is not descended into. None (default)
            descends into every directory.
        min_depth: Minimum inclusion depth (>= 1, direct children of
            `root` are at depth 1). Defaults to 1.
        max_depth: Maximum inclusion depth (>= `min_depth`), or None for
            unlimited. Defaults to None.
        ordered: Sort results lexicographically. Defaults to True.
        stringify: Return paths as strings instead of `Path`. Defaults to
            False.

    Returns:
        A sequence of `Path` (or `str` if `stringify=True`) including
        both files and directories that pass every filter.

    Raises:
        ValueError: Invalid depth bounds (`min_depth < 1`, `max_depth < 1`,
            or `min_depth > max_depth`), or `part_filter` / `name_filter`
            is a dict that cannot be deserialized.
        DirectoryNotFoundError: `root` does not exist.
        NotADirectoryError: `root` exists but is not a directory.
    """
    return PathSearch.run(root, stringify=stringify, **options)


@overload
def search_files(
    root: StrPath, *, stringify: Literal[False] = False, **options: Unpack[SearchKwargs]
) -> list[Path]: ...


@overload
def search_files(
    root: StrPath, *, stringify: Literal[True], **options: Unpack[SearchKwargs]
) -> list[str]: ...


@overload
def search_files(
    root: StrPath, *, stringify: bool, **options: Unpack[SearchKwargs]
) -> list[Path] | list[str]: ...


def search_files(
    root: StrPath, *, stringify: bool = False, **options: Unpack[SearchKwargs]
) -> list[Path] | list[str]:
    """Walk `root` and return file paths that match.

    Files are returned if they pass `part_filter` (on the visited
    directory's relative path), `name_filter` (on the file's leaf name),
    `predicate` (on the file's full `Path`), and lie within
    `[min_depth, max_depth]`. Sub-directories are walked into but never
    themselves returned.

    Keyword Args:
        part_filter: Filter on each visited directory's relative path
            string. Accepts a `Filter` or a `FilterDict`. None (default)
            accepts all directories.
        name_filter: Filter on each file's leaf name. Accepts a `Filter`
            or a `FilterDict`. None (default) accepts all names.
        predicate: Callable on each file's full `Path` for a final check.
            None (default) accepts all paths.
        exclude: Paths to skip: a `StrPath` (absolute under `root` or
            root-relative), a `Filter` (on the root-relative POSIX path), a
            `Callable` on the candidate `Path`, or an iterable of these
            (OR-combined). An excluded *directory* is pruned (its subtree is
            not descended). None (default) excludes nothing.
        descend: Callable on each sub-directory's full `Path` deciding whether
            to visit it. A directory that fails is not descended into. None
            (default) descends into every directory.
        min_depth: Minimum inclusion depth (>= 1, direct children of
            `root` are at depth 1). Defaults to 1.
        max_depth: Maximum inclusion depth (>= `min_depth`), or None for
            unlimited. Defaults to None.
        ordered: Sort results lexicographically. Defaults to True.
        stringify: Return paths as strings instead of `Path`. Defaults to
            False.

    Returns:
        A sequence of `Path` (or `str` if `stringify=True`) of files
        that pass every filter.

    Raises:
        ValueError: Invalid depth bounds (`min_depth < 1`, `max_depth < 1`,
            or `min_depth > max_depth`), or `part_filter` / `name_filter`
            is a dict that cannot be deserialized.
        DirectoryNotFoundError: `root` does not exist.
        NotADirectoryError: `root` exists but is not a directory.
    """
    return FileSearch.run(root, stringify=stringify, **options)


@overload
def search_dirs(
    root: StrPath, *, stringify: Literal[False] = False, **options: Unpack[SearchKwargs]
) -> list[Path]: ...


@overload
def search_dirs(
    root: StrPath, *, stringify: Literal[True], **options: Unpack[SearchKwargs]
) -> list[str]: ...


@overload
def search_dirs(
    root: StrPath, *, stringify: bool, **options: Unpack[SearchKwargs]
) -> list[Path] | list[str]: ...


def search_dirs(
    root: StrPath, *, stringify: bool = False, **options: Unpack[SearchKwargs]
) -> list[Path] | list[str]:
    """Walk `root` and return directory paths that match.

    Sub-directories are returned if they pass `part_filter` (on the visited
    *parent* directory's relative path), `name_filter` (on the
    sub-directory's leaf name), `predicate` (on its full `Path`), and lie
    within `[min_depth, max_depth]`. Files are never returned. `root` itself
    is not included.

    Keyword Args:
        part_filter: Filter on each visited directory's relative path
            string. Accepts a `Filter` or a `FilterDict`. None (default)
            accepts all directories.
        name_filter: Filter on each sub-directory's leaf name. Accepts a
            `Filter` or a `FilterDict`. None (default) accepts all names.
        predicate: Callable on each sub-directory's full `Path` for a
            final check. None (default) accepts all paths.
        exclude: Paths to skip: a `StrPath` (absolute under `root` or
            root-relative), a `Filter` (on the root-relative POSIX path), a
            `Callable` on the candidate `Path`, or an iterable of these
            (OR-combined). An excluded *directory* is pruned (its subtree is
            not descended). None (default) excludes nothing.
        descend: Callable on each sub-directory's full `Path` deciding whether
            to visit it. A directory that fails is still offered to the filters
            and may be returned, but is not descended into. None (default)
            descends into every directory.
        min_depth: Minimum inclusion depth (>= 1, direct sub-directories
            of `root` are at depth 1). Defaults to 1.
        max_depth: Maximum inclusion depth (>= `min_depth`), or None for
            unlimited. Defaults to None.
        ordered: Sort results lexicographically. Defaults to True.
        stringify: Return paths as strings instead of `Path`. Defaults to
            False.

    Returns:
        A sequence of `Path` (or `str` if `stringify=True`) of
        sub-directories that pass every filter.

    Raises:
        ValueError: Invalid depth bounds (`min_depth < 1`, `max_depth < 1`,
            or `min_depth > max_depth`), or `part_filter` / `name_filter`
            is a dict that cannot be deserialized.
        DirectoryNotFoundError: `root` does not exist.
        NotADirectoryError: `root` exists but is not a directory.
    """
    return DirSearch.run(root, stringify=stringify, **options)

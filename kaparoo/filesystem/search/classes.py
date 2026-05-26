from __future__ import annotations

__all__ = ("DirSearch", "FileSearch", "PathSearch", "Search")

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.existence import ensure_dir_exists
from kaparoo.filesystem.utils import stringify_path, stringify_paths

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path
    from typing import Literal

    from kaparoo.filesystem.types import StrPath

    # TODO(filter): placeholder for the `part_filter` / `name_filter`
    # inputs; replace `object` with the real `Filter` type once it is
    # designed.
    type _Filters = Sequence[object]


# `search_paths` / `search_files` / `search_dirs` (in `wrappers`) will
# replace `get_paths` / `get_files` / `get_dirs` (in `deprecated`). The
# class hierarchy below is internal -- it exists to share the walk
# logic, not as a user-facing API. This is a skeleton: the `Path.walk`
# traversal, depth limiting, collection and `stringify` handling are
# implemented; the `part_filter` / `name_filter` methods
# (`_accept_part` / `_accept_name`) are stubs and subtree pruning is
# not done (search for "TODO(filter)").


class Search(ABC):
    """Internal base class shared by the `search_*` functions.

    Stateless: subclasses are namespaces with no instance state.
    `_select` chooses which entry kinds to collect; `run` implements the
    walk. Not part of the public API -- prefer `search_paths`,
    `search_files`, `search_dirs`.
    """

    @classmethod
    @abstractmethod
    def _select(cls, dirnames: list[str], filenames: list[str], /) -> list[str]:
        """Return the entry names to collect at one walked directory."""
        raise NotImplementedError

    @classmethod
    def _accept_part(
        cls,
        part: str,  # noqa: ARG003
        filters: _Filters | None,  # noqa: ARG003
        /,
    ) -> bool:
        """Whether entries under a directory with this `part` are eligible.

        `part` is the directory's path relative to the search root.
        """
        # TODO(filter): apply `part_filter`.
        return True

    @classmethod
    def _accept_name(
        cls,
        name: str,  # noqa: ARG003
        filters: _Filters | None,  # noqa: ARG003
        /,
    ) -> bool:
        """Whether an entry with this basename is included."""
        # TODO(filter): apply `name_filter`.
        return True

    @overload
    @classmethod
    def run(
        cls,
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
    @classmethod
    def run(
        cls,
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
    @classmethod
    def run(
        cls,
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

    @classmethod
    def run(
        cls,
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
        """Walk `root` and return the matching paths.

        A direct child of `root` has depth 1; `max_depth` of None means
        unlimited.

        Work in progress: `part_filter` / `name_filter` are not
        implemented yet -- see TODO(filter).

        Raises:
            ValueError: If `min_depth` or `max_depth` is not a positive int
                (`max_depth` may also be None), or if `min_depth` exceeds
                `max_depth`.
            DirectoryNotFoundError: If `root` does not exist.
            NotADirectoryError: If `root` is not a directory.
        """
        if min_depth < 1:
            msg = f"min_depth must be positive (got {min_depth})"
            raise ValueError(msg)
        if max_depth is not None and max_depth < 1:
            msg = f"max_depth must be positive or None (got {max_depth})"
            raise ValueError(msg)
        if max_depth is not None and min_depth > max_depth:
            msg = f"min_depth ({min_depth}) cannot exceed max_depth ({max_depth})"
            raise ValueError(msg)

        root = ensure_dir_exists(root)
        root_depth = len(root.parts)

        results: list[Path] = []

        for dirpath, dirnames, filenames in root.walk():
            # Depth of the entries in `dirnames` / `filenames`; a direct
            # child of `root` has depth 1.
            child_depth = len(dirpath.parts) - root_depth + 1

            # `part` is this directory's path relative to `root`.
            part_str = stringify_path(dirpath.relative_to(root))

            # TODO(filter): when `_accept_part` rejects via a prunable
            # filter, also prune the subtree by clearing `dirnames`.

            # `max_depth` is enforced by the prune below (the walk never
            # descends past it), so collection only needs the `min_depth`
            # lower bound.
            if child_depth >= min_depth and cls._accept_part(part_str, part_filter):
                names = cls._select(dirnames, filenames)
                results.extend(
                    dirpath / n for n in names if cls._accept_name(n, name_filter)
                )

            # Stop descending once the next level down would exceed `max_depth`.
            if max_depth is not None and child_depth >= max_depth:
                dirnames.clear()

        if callable(predicate):
            results = [p for p in results if predicate(p)]

        if ordered:
            results.sort()

        return stringify_paths(results) if stringify else results


class PathSearch(Search):
    """Search for both directories and files."""

    @classmethod
    def _select(cls, dirnames: list[str], filenames: list[str], /) -> list[str]:
        return [*dirnames, *filenames]


class FileSearch(Search):
    """Search for files."""

    @classmethod
    def _select(cls, _dirnames: list[str], filenames: list[str], /) -> list[str]:
        return list(filenames)


class DirSearch(Search):
    """Search for directories."""

    @classmethod
    def _select(cls, dirnames: list[str], _filenames: list[str], /) -> list[str]:
        return list(dirnames)

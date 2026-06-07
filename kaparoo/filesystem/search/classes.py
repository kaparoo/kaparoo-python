from __future__ import annotations

__all__ = ("DirSearch", "FileSearch", "PathSearch", "Search")

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.existence import ensure_dir_exists
from kaparoo.filesystem.utils import stringify_path, stringify_paths
from kaparoo.filters import Filter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from pathlib import Path
    from typing import Literal

    from kaparoo.filesystem.types import StrPath
    from kaparoo.filters.types import FilterDict


class Search(ABC):
    """Stateless internal base for `search_*`; prefer those over direct use."""

    @classmethod
    @abstractmethod
    def _select_names(cls, dirnames: list[str], filenames: list[str], /) -> list[str]:
        raise NotImplementedError

    @classmethod
    def _filter_names(
        cls, names: Iterable[str], pattern: Filter | None, /
    ) -> list[str]:
        if pattern is None:
            return list(names)
        return [name for name in names if pattern.matches(name)]

    @classmethod
    def _validate_depth_range(cls, min_depth: int, max_depth: int | None) -> None:
        if min_depth < 1:
            msg = f"min_depth must be positive (got {min_depth})"
            raise ValueError(msg)
        if max_depth is not None and max_depth < 1:
            msg = f"max_depth must be positive or None (got {max_depth})"
            raise ValueError(msg)
        if max_depth is not None and min_depth > max_depth:
            msg = f"min_depth ({min_depth}) cannot exceed max_depth ({max_depth})"
            raise ValueError(msg)

    @overload
    @classmethod
    def run(
        cls,
        root: StrPath,
        *,
        part_filter: Filter | FilterDict | None = None,
        name_filter: Filter | FilterDict | None = None,
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
        part_filter: Filter | FilterDict | None = None,
        name_filter: Filter | FilterDict | None = None,
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
        part_filter: Filter | FilterDict | None = None,
        name_filter: Filter | FilterDict | None = None,
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
        part_filter: Filter | FilterDict | None = None,
        name_filter: Filter | FilterDict | None = None,
        predicate: Callable[[Path], bool] | None = None,
        min_depth: int = 1,
        max_depth: int | None = None,
        ordered: bool = True,
        stringify: bool = False,
    ) -> Sequence[Path] | Sequence[str]:
        """Walk `root` and return matching paths.

        At each visited directory, candidate entries (the set selected by
        the subclass) pass through three filters in order:

            1. `part_filter` -- applied to the visited directory's relative
               path string. Directories that don't pass yield no entries,
               but their sub-directories are still visited.
            2. `name_filter` -- applied to each entry's leaf name.
            3. `predicate`   -- applied to each surviving entry's full
               `Path`.

        Depth is measured from `root`: a direct child of `root` is at depth
        1. Entries below `min_depth` are skipped but the walk still descends
        through them. Entries at `max_depth` are included, but their
        descendants are not visited. `max_depth=None` means unbounded.

        Args:
            root: The directory to walk.
            part_filter: Filter applied to each visited directory's relative
                path string. Accepts a `Filter` or a `FilterDict`. None
                (default) accepts all directories.
            name_filter: Filter applied to each candidate entry's leaf name.
                Accepts a `Filter` or a `FilterDict`. None (default)
                accepts all names.
            predicate: Callable applied to each surviving `Path` for a final
                boolean check. None (default) accepts all paths.
            min_depth: Minimum inclusion depth (must be >= 1). Defaults to 1.
            max_depth: Maximum inclusion depth (must be >= `min_depth`), or
                None for unlimited. Defaults to None.
            ordered: If True (default), sort results by `Path` lexicographic
                order. If False, results follow OS-defined walk order.
            stringify: If True, return each path as a string. If False
                (default), return `Path` objects.

        Returns:
            A sequence of `Path` (or `str` if `stringify=True`) for entries
            that pass every filter.

        Raises:
            ValueError: If `min_depth < 1`, `max_depth < 1`,
                `min_depth > max_depth`, or `part_filter` / `name_filter`
                is a dict that cannot be deserialized.
            DirectoryNotFoundError: If `root` does not exist.
            NotADirectoryError: If `root` exists but is not a directory.
        """
        cls._validate_depth_range(min_depth, max_depth)

        if part_filter is not None:
            part_filter = Filter.parse(part_filter)
        if name_filter is not None:
            name_filter = Filter.parse(name_filter)

        root = ensure_dir_exists(root)
        root_depth = len(root.parts)
        results: list[Path] = []

        for dirpath, dirnames, filenames in root.walk():
            child_depth = len(dirpath.parts) - root_depth + 1

            if child_depth >= min_depth and (
                part_filter is None
                or part_filter.matches(stringify_path(dirpath, after=root))
            ):
                names = cls._select_names(dirnames, filenames)
                names = cls._filter_names(names, name_filter)

                paths = (dirpath / name for name in names)
                if callable(predicate):
                    paths = (path for path in paths if predicate(path))

                results.extend(paths)

            if max_depth is not None and child_depth >= max_depth:
                dirnames.clear()  # prune deeper subtree; `Path.walk` honors in-place mutation

        if ordered:
            results.sort()

        return stringify_paths(results) if stringify else results


class PathSearch(Search):
    @classmethod
    def _select_names(cls, dirnames: list[str], filenames: list[str], /) -> list[str]:
        return [*dirnames, *filenames]


class FileSearch(Search):
    @classmethod
    def _select_names(cls, _dirnames: list[str], filenames: list[str], /) -> list[str]:
        return list(filenames)


class DirSearch(Search):
    @classmethod
    def _select_names(cls, dirnames: list[str], _filenames: list[str], /) -> list[str]:
        return list(dirnames)

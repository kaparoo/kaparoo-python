from __future__ import annotations

__all__ = ("DirSearch", "FileSearch", "PathSearch", "Search")

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.exclude import build_excluder
from kaparoo.filesystem.existence import ensure_dir_exists
from kaparoo.filesystem.utils import stringify_path, stringify_paths
from kaparoo.filters import Filter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from pathlib import Path
    from typing import Literal

    from kaparoo.filesystem.exclude import Excluder
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
    def _part_ok(cls, part_filter: Filter | None, dirpath: Path, root: Path) -> bool:
        """Whether `dirpath` passes `part_filter` (a `None` filter admits any).

        Stringifies the path only when a filter is set, so an unused
        `part_filter` skips the per-directory work.
        """
        if part_filter is None:
            return True
        return part_filter.matches(stringify_path(dirpath, after=root))

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
        exclude: Excluder | Iterable[Excluder] | None = None,
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
        exclude: Excluder | Iterable[Excluder] | None = None,
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
        exclude: Excluder | Iterable[Excluder] | None = None,
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
        exclude: Excluder | Iterable[Excluder] | None = None,
        min_depth: int = 1,
        max_depth: int | None = None,
        ordered: bool = True,
        stringify: bool = False,
    ) -> Sequence[Path] | Sequence[str]:
        """Walk `root` and return the entries matching the configured filters.

        The shared engine behind `search_paths` / `search_files` /
        `search_dirs`, which document the parameters. At each visited
        directory the subclass's candidate entries pass three filters in
        order:

            1. `part_filter` -- the visited directory's relative path string;
               a directory that fails yields no entries but is still
               descended.
            2. `name_filter` -- each candidate entry's leaf name.
            3. `predicate`   -- each surviving entry's full `Path`.

        `exclude` is applied before those gates: excluded entries are dropped
        and an excluded *directory* is pruned (its subtree is never visited),
        which the filters cannot do (a directory failing `name_filter` is
        still descended).

        Depth is measured from `root` (a direct child is depth 1): entries
        below `min_depth` are skipped but still descended, and entries at
        `max_depth` are included but not descended past.
        """
        cls._validate_depth_range(min_depth, max_depth)

        if part_filter is not None:
            part_filter = Filter.parse(part_filter)
        if name_filter is not None:
            name_filter = Filter.parse(name_filter)

        root = ensure_dir_exists(root)
        root_depth = len(root.parts)

        excluder = build_excluder(exclude, root)

        has_excluder = excluder is not None
        has_predicate = predicate is not None
        has_max_depth = max_depth is not None

        results: list[Path] = []

        for dirpath, dirnames, filenames in root.walk():
            child_depth = len(dirpath.parts) - root_depth + 1

            if has_excluder:
                dirnames[:] = [d for d in dirnames if not excluder(dirpath / d)]

            if child_depth >= min_depth and cls._part_ok(part_filter, dirpath, root):
                names = cls._select_names(dirnames, filenames)
                names = cls._filter_names(names, name_filter)

                paths = (dirpath / name for name in names)
                if has_excluder:
                    paths = (p for p in paths if not excluder(p))
                if has_predicate:
                    paths = (p for p in paths if predicate(p))

                results.extend(paths)

            if has_max_depth and child_depth >= max_depth:
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

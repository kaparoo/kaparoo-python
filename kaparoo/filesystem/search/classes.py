from __future__ import annotations

__all__ = ("DirSearch", "FileSearch", "PathSearch", "Search")

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.existence import ensure_dir_exists
from kaparoo.filesystem.utils import stringify_path, stringify_paths

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from pathlib import Path
    from typing import Literal

    from kaparoo.filesystem.search.filters import Filter
    from kaparoo.filesystem.types import StrPath


class Search(ABC):
    """Stateless internal base for `search_*`; prefer those over direct use."""

    @classmethod
    @abstractmethod
    def _select_names(
        cls, dirnames: list[str], filenames: list[str], /
    ) -> list[str]: ...

    @classmethod
    def _filter_part(cls, part: str, filter: Filter | None, /) -> bool:  # noqa: A002
        return True if filter is None else filter.matches(part)

    @classmethod
    def _filter_name(cls, name: str, filter: Filter | None, /) -> bool:  # noqa: A002
        return True if filter is None else filter.matches(name)

    @classmethod
    def _filter_names(cls, names: Iterable[str], filter: Filter | None, /) -> list[str]:  # noqa: A002
        if filter is None:
            return list(names)
        return [name for name in names if cls._filter_name(name, filter)]

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
        part_filter: Filter | None = None,
        name_filter: Filter | None = None,
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
        part_filter: Filter | None = None,
        name_filter: Filter | None = None,
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
        part_filter: Filter | None = None,
        name_filter: Filter | None = None,
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
        part_filter: Filter | None = None,
        name_filter: Filter | None = None,
        predicate: Callable[[Path], bool] | None = None,
        min_depth: int = 1,
        max_depth: int | None = None,
        ordered: bool = True,
        stringify: bool = False,
    ) -> Sequence[Path] | Sequence[str]:
        """Walk `root` and return matching paths.

        A direct child of `root` has depth 1; `max_depth=None` is unlimited.

        Raises:
            ValueError: invalid `min_depth` or `max_depth`.
            DirectoryNotFoundError: `root` does not exist.
            NotADirectoryError: `root` is not a directory.
        """
        cls._validate_depth_range(min_depth, max_depth)

        root = ensure_dir_exists(root)
        root_depth = len(root.parts)
        results: list[Path] = []

        for dirpath, dirnames, filenames in root.walk():
            child_depth = len(dirpath.parts) - root_depth + 1
            part = stringify_path(dirpath.relative_to(root))

            if child_depth >= min_depth and cls._filter_part(part, part_filter):
                names = cls._select_names(dirnames, filenames)
                names = cls._filter_names(names, name_filter)
                results.extend(dirpath / name for name in names)

            if max_depth is not None and child_depth >= max_depth:
                dirnames.clear()

        if callable(predicate):
            results = [p for p in results if predicate(p)]

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

from __future__ import annotations

__all__ = (
    "DirSearch",
    "FileSearch",
    "PathSearch",
    "get_dirs",
    "get_files",
    "get_paths",
)

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.existence import dir_exists, ensure_dir_exists, file_exists
from kaparoo.filesystem.utils import stringify_path, stringify_paths

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths

    # TODO(filter): placeholder for the `part` / `name` filter inputs;
    # replace `object` with the real `Filter` type once it is designed.
    type _Filters = Sequence[object]


@overload
def get_paths(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def get_paths(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def get_paths(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def get_paths(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Get paths that match the specified criteria.

    The criteria are applied in the following order:
        `pattern` -> `excludes` -> `condition`

    Args:
        root: The root directory to search.
        pattern: The glob pattern to search for. Defaults to "*".
        excludes: A sequence of paths to exclude from the search. Both absolute
            and relative paths are supported. Defaults to None.
        condition: A predicate function to filter the paths. Only paths that satisfy
            the predicate are returned. Defaults to None.
        recursive: Whether to search recursively in the root directory. Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The paths that match the specified criteria as a sequence of Path objects
            or strings, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If the root directory does not exist.
        NotADirectoryError: If the root directory is not a directory.
    """
    root = ensure_dir_exists(root)

    paths = list(root.rglob(pattern) if recursive else root.glob(pattern))

    excludes_set = {root}
    if excludes:
        resolve = lambda p: p if p.is_relative_to(root) else root / p  # noqa: E731
        excludes_set.update(resolve(Path(e)) for e in excludes)

    paths = [p for p in paths if p not in excludes_set]

    if callable(condition):
        paths = [p for p in paths if condition(p)]

    return stringify_paths(paths) if stringify else paths


@overload
def get_files(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def get_files(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def get_files(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def get_files(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Get file paths that match the specified criteria.

    The criteria are applied in the following order:
        `pattern` -> `excludes` -> `condition`

    Args:
        root: The root directory to search.
        pattern: The glob pattern to search for. Defaults to "*".
        excludes: A sequence of paths to exclude from the search. Both absolute
            and relative paths are supported. Defaults to None.
        condition: A predicate function to filter the paths. Only paths that satisfy
            the predicate are returned. Defaults to None.
        recursive: Whether to search recursively in the root directory. Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The file paths that match the specified criteria as a sequence of Path objects
            or strings, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If the root directory does not exist.
        NotADirectoryError: If the root directory is not a directory.
    """
    if callable(condition):
        file_condition = lambda path: file_exists(path) and condition(path)  # noqa: E731
    else:
        file_condition = file_exists

    return get_paths(
        root,
        pattern=pattern,
        excludes=excludes,
        condition=file_condition,
        recursive=recursive,
        stringify=stringify,
    )


@overload
def get_dirs(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def get_dirs(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def get_dirs(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def get_dirs(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    recursive: bool = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Get directory paths that match the specified criteria.

    The criteria are applied in the following order:
        `pattern` -> `excludes` -> `condition`

    Args:
        root: The root directory to search.
        pattern: The glob pattern to search for. Defaults to "*".
        excludes: A sequence of paths to exclude from the search. Both absolute
            and relative paths are supported. Defaults to None.
        condition: A predicate function to filter the paths. Only paths that satisfy
            the predicate are returned. Defaults to None.
        recursive: Whether to search recursively in the root directory. Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The directory paths that match the specified criteria as a sequence of
            Path objects or strings, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If the root directory does not exist.
        NotADirectoryError: If the root directory is not a directory.
    """
    if callable(condition):
        dir_condition = lambda path: dir_exists(path) and condition(path)  # noqa: E731
    else:
        dir_condition = dir_exists

    return get_paths(
        root,
        pattern=pattern,
        excludes=excludes,
        condition=dir_condition,
        recursive=recursive,
        stringify=stringify,
    )


# New search API (work in progress).
#
# `PathSearch` / `FileSearch` / `DirSearch` will replace
# `get_paths` / `get_dirs` / `get_files`. Each is a configured, reusable
# search object: construct it with the search criteria, then call
# `run(root)`. This is a skeleton -- the `Path.walk` traversal, depth
# limiting, collection and `stringify` handling are implemented; the
# `part` / `name` filter methods (`_accept_part` / `_accept_name`) are
# stubs and subtree pruning is not done (search for "TODO(filter)").


class Search(ABC):
    """Abstract base for `PathSearch` / `FileSearch` / `DirSearch`.

    Stateless: subclasses are namespaces with no instance state.
    `_select` chooses which entry kinds to collect; `run` implements the
    walk and is the only public entry point.
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
        # TODO(filter): apply the `part` filters.
        return True

    @classmethod
    def _accept_name(
        cls,
        name: str,  # noqa: ARG003
        filters: _Filters | None,  # noqa: ARG003
        /,
    ) -> bool:
        """Whether an entry with this basename is included."""
        # TODO(filter): apply the `name` filters.
        return True

    @overload
    @classmethod
    def run(
        cls,
        root: StrPath,
        *,
        part: _Filters | None = None,
        name: _Filters | None = None,
        condition: Callable[[Path], bool] | None = None,
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
        part: _Filters | None = None,
        name: _Filters | None = None,
        condition: Callable[[Path], bool] | None = None,
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
        part: _Filters | None = None,
        name: _Filters | None = None,
        condition: Callable[[Path], bool] | None = None,
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
        part: _Filters | None = None,
        name: _Filters | None = None,
        condition: Callable[[Path], bool] | None = None,
        min_depth: int = 1,
        max_depth: int | None = None,
        ordered: bool = True,
        stringify: bool = False,
    ) -> Sequence[Path] | Sequence[str]:
        """Walk `root` and return the matching paths.

        A direct child of `root` has depth 1; `max_depth` of None means
        unlimited.

        Work in progress: the `part` / `name` filtering is not implemented
        yet -- see TODO(filter).

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
            if child_depth >= min_depth and cls._accept_part(part_str, part):
                names = cls._select(dirnames, filenames)
                results.extend(dirpath / n for n in names if cls._accept_name(n, name))

            # Stop descending once the next level down would exceed `max_depth`.
            if max_depth is not None and child_depth >= max_depth:
                dirnames.clear()

        if callable(condition):
            results = [p for p in results if condition(p)]

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

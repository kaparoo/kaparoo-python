from __future__ import annotations

__all__ = ("get_dirs", "get_files", "get_paths")

from pathlib import Path
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.existence import dir_exists, ensure_dir_exists, file_exists
from kaparoo.filesystem.utils import stringify_paths

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


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

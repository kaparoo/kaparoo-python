from __future__ import annotations

__all__ = (
    # make
    "make_dirs",
    # empty
    "dir_empty",
    "dirs_empty",
    # search
    "get_paths",
    "get_files",
    "get_dirs",
)

import os
import random
from pathlib import Path
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.existence import (
    _join_root_if_provided,
    dir_exists,
    ensure_dir_exists,
    ensure_dirs_exist,
    file_exists,
)
from kaparoo.filesystem.utils import stringify_paths

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


# ========================== #
#            Make            #
# ========================== #


def make_dirs(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    mode: int = 0o777,
    exist_ok: bool = False,
) -> StrPaths:
    """Recursively create directories.

    Args:
        paths: The directory paths to create.
        root: The root directory to prepend to each path. Defaults to None.
        mode: The mode to use when creating the directories. Defaults to 0o777.
        exist_ok: Whether to suppress OSError if any of the paths already exist.
            Defaults to False.

    Returns:
        The directory paths that were created.

    Raises:
        DirectoryNotFoundError: If `root` is provided and does not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        ValueError: If `root` is provided and any of the paths are absolute.
        OSError: If `exist_ok` is False and any of the paths already exist.
        OSError: If any of the paths are not directories.
    """
    paths = _join_root_if_provided(paths, root)
    for path in paths:
        os.makedirs(path, mode, exist_ok)
    return paths


# ========================== #
#            Empty           #
# ========================== #


def dir_empty_unsafe(path: StrPath) -> bool:
    """Check if a directory is empty without existence checks."""
    with os.scandir(path) as it:
        return not any(it)


def dirs_empty_unsafe(paths: StrPaths, root: StrPath | None = None) -> bool:
    """Check if directories are empty without existence checks."""
    if root is not None:
        paths = [os.path.join(root, p) for p in paths]
    return all(dir_empty_unsafe(p) for p in paths)


def dir_empty(path: StrPath) -> bool:
    """Check if a directory is empty.

    Args:
        path: The directory path to check.

    Returns:
        True if the directory is empty, False otherwise.

    Raises:
        DirectoryNotFoundError: If the path does not exist.
        NotADirectoryError: If the path is not a directory.
    """
    path = ensure_dir_exists(path)
    return dir_empty_unsafe(path)


def dirs_empty(paths: StrPaths, root: StrPath | None = None) -> bool:
    """Check if directories are empty.

    Args:
        paths: A sequence of directory paths to check.
        root: The root directory to prepend to each path. Defaults to None.

    Returns:
        True if all directories are empty, False otherwise.

    Raises:
        DirectoryNotFoundError: If `root` is provided and does not exist.
        DirectoryNotEmptyError: If any of the paths do not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        NotADirectoryError: If any of the paths are not directories.
        ValueError: If `root` is provided and any of the paths are absolute.
    """
    paths = ensure_dirs_exist(paths, root=root)
    return all(dir_empty_unsafe(p) for p in paths)


# ========================== #
#           Search           #
# ========================== #


@overload
def get_paths(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    num_samples: int | None = None,
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
    num_samples: int | None = None,
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
    num_samples: int | None = None,
    recursive: bool = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def get_paths(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    num_samples: int | None = None,
    recursive: bool = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Get paths that match the specified criteria.

    The criteria are applied in the following order:
        `pattern` -> `excludes` -> `condition` -> `num_samples`

    Args:
        root: The root directory to search.
        pattern: The glob pattern to search for. Defaults to "*".
        excludes: A sequence of paths to exclude from the search. Both absolute
            and relative paths are supported. Defaults to None.
        condition: A predicate function to filter the paths. Only paths that satisfy
            the predicate are returned. Defaults to None.
        num_samples: The maximum number of paths to return. If provided, only the
            `num_samples` paths are randomly selected and returned. Defaults to None.
        recursive: Whether to search recursively in the root directory. Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The paths that match the specified criteria as a sequence of Path objects
            or strings, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If the root directory does not exist.
        NotADirectoryError: If the root directory is not a directory.
        ValueError: If `num_samples` is not greater than 0.
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

    if isinstance(num_samples, int) and num_samples < len(paths):
        if num_samples <= 0:
            raise ValueError(f"num_samples must be greater than 0 (got {num_samples})")
        paths = random.sample(paths, num_samples)

    return stringify_paths(paths) if stringify else paths


@overload
def get_files(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    num_samples: int | None = None,
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
    num_samples: int | None = None,
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
    num_samples: int | None = None,
    recursive: bool = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def get_files(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    num_samples: int | None = None,
    recursive: bool = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Get file paths that match the specified criteria.

    The criteria are applied in the following order:
        `pattern` -> `excludes` -> `condition` -> `num_samples`

    Args:
        root: The root directory to search.
        pattern: The glob pattern to search for. Defaults to "*".
        excludes: A sequence of paths to exclude from the search. Both absolute
            and relative paths are supported. Defaults to None.
        condition: A predicate function to filter the paths. Only paths that satisfy
            the predicate are returned. Defaults to None.
        num_samples: The maximum number of paths to return. If provided, only the
            `num_samples` paths are randomly selected and returned. Defaults to None.
        recursive: Whether to search recursively in the root directory. Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The file paths that match the specified criteria as a sequence of Path objects
            or strings, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If the root directory does not exist.
        NotADirectoryError: If the root directory is not a directory.
        ValueError: If `num_samples` is not greater than 0.
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
        num_samples=num_samples,
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
    num_samples: int | None = None,
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
    num_samples: int | None = None,
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
    num_samples: int | None = None,
    recursive: bool = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def get_dirs(
    root: StrPath,
    *,
    pattern: str = "*",
    excludes: StrPaths | None = None,
    condition: Callable[[Path], bool] | None = None,
    num_samples: int | None = None,
    recursive: bool = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Get directory paths that match the specified criteria.

    The criteria are applied in the following order:
        `pattern` -> `excludes` -> `condition` -> `num_samples`

    Args:
        root: The root directory to search.
        pattern: The glob pattern to search for. Defaults to "*".
        excludes: A sequence of paths to exclude from the search. Both absolute
            and relative paths are supported. Defaults to None.
        condition: A predicate function to filter the paths. Only paths that satisfy
            the predicate are returned. Defaults to None.
        num_samples: The maximum number of paths to return. If provided, only the
            `num_samples` paths are randomly selected and returned. Defaults to None.
        recursive: Whether to search recursively in the root directory. Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The directory paths that match the specified criteria as a sequence of
            Path objects or strings, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If the root directory does not exist.
        NotADirectoryError: If the root directory is not a directory.
        ValueError: If `num_samples` is not greater than 0.
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
        num_samples=num_samples,
        recursive=recursive,
        stringify=stringify,
    )

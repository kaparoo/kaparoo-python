from __future__ import annotations

__all__ = ("dir_empty", "dirs_empty", "make_dir", "make_dirs")

import os
from pathlib import Path
from typing import TYPE_CHECKING

from kaparoo.filesystem.existence import (
    _join_root_if_provided,
    _validate_mode,
    ensure_dir_exists,
    ensure_dirs_exist,
)

if TYPE_CHECKING:
    from kaparoo.filesystem.types import StrPath, StrPaths


# ========================== #
#            Make            #
# ========================== #


def make_dir(path: StrPath, *, mode: int = 0o777, exist_ok: bool = False) -> Path:
    """Recursively create a directory.

    Args:
        path: The directory path to create.
        mode: The mode to use when creating the directory. Defaults to 0o777.
        exist_ok: Whether to suppress OSError if the path already exists.
            Defaults to False.

    Returns:
        The directory path that was created.

    Raises:
        ValueError: If `mode` is outside the range 0o1-0o7777
            (not checked on Windows, where the mode is ignored).
        OSError: If `exist_ok` is False and the path already exists.
        OSError: If the path is not a directory.
    """
    _validate_mode(mode)
    path = Path(path)
    path.mkdir(mode=mode, parents=True, exist_ok=exist_ok)
    return path


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
        ValueError: If `mode` is outside the range 0o1-0o7777
            (not checked on Windows, where the mode is ignored).
        DirectoryNotFoundError: If `root` is provided and does not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        ValueError: If `root` is provided and any of the paths are absolute.
        OSError: If `exist_ok` is False and any of the paths already exist.
        OSError: If any of the paths are not directories.
    """
    _validate_mode(mode)
    paths = _join_root_if_provided(paths, root)
    for path in paths:
        Path(path).mkdir(mode=mode, parents=True, exist_ok=exist_ok)
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
        paths = [Path(root) / p for p in paths]
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
        DirectoryNotFoundError: If any of the paths do not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        NotADirectoryError: If any of the paths are not directories.
        ValueError: If `root` is provided and any of the paths are absolute.
    """
    paths = ensure_dirs_exist(paths, root=root)
    return all(dir_empty_unsafe(p) for p in paths)

from __future__ import annotations

__all__ = (
    "dir_empty",
    "dir_empty_unsafe",
    "dir_not_empty",
    "dir_not_empty_unsafe",
    "dirs_empty",
    "dirs_empty_unsafe",
    "dirs_not_empty",
    "dirs_not_empty_unsafe",
    "make_dir",
    "make_dirs",
)

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.existence import (
    _join_root_if_provided,
    _validate_mode,
    ensure_dir_exists,
    ensure_dirs_exist,
)
from kaparoo.filesystem.utils import stringify_path, stringify_paths

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


# ========================== #
#            Make            #
# ========================== #


@overload
def make_dir(
    path: StrPath,
    *,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: Literal[False] = False,
) -> Path: ...


@overload
def make_dir(
    path: StrPath,
    *,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: Literal[True],
) -> str: ...


@overload
def make_dir(
    path: StrPath,
    *,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: bool,
) -> Path | str: ...


def make_dir(
    path: StrPath,
    *,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: bool = False,
) -> Path | str:
    """Recursively create a directory.

    Args:
        path: The directory path to create.
        mode: The mode to use when creating the directory. Defaults to 0o777.
        exist_ok: Whether to suppress OSError if the path already exists.
            Defaults to False.
        clean: Whether to recreate the directory empty when it already exists,
            removing its contents first. Only an existing *directory* is wiped;
            a non-directory still raises. Because the directory is removed and
            remade, `clean=True` makes `exist_ok` moot. **Destructive.**
            Defaults to False.
        stringify: Whether to return the path as a string. Defaults to False.

    Returns:
        The created directory path as a Path object or a string,
            depending on the value of `stringify`.

    Raises:
        ValueError: If `mode` is outside the range 0o1-0o7777
            (not checked on Windows, where the mode is ignored).
        NotADirectoryError: If the path exists but is not a directory.
        OSError: If `exist_ok` is False, `clean` is False, and the path
            already exists.
    """
    _validate_mode(mode)
    path = Path(path)
    if path.exists() and not path.is_dir():
        msg = f"not a directory: {path}"
        raise NotADirectoryError(msg)
    if clean and path.is_dir():
        shutil.rmtree(path)
    path.mkdir(mode=mode, parents=True, exist_ok=exist_ok)
    return stringify_path(path) if stringify else path


@overload
def make_dirs(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def make_dirs(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def make_dirs(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def make_dirs(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Recursively create directories.

    Args:
        paths: The directory paths to create.
        root: The root directory to prepend to each path. Defaults to None.
        mode: The mode to use when creating the directories. Defaults to 0o777.
        exist_ok: Whether to suppress OSError if any of the paths already exist.
            Defaults to False.
        clean: Whether to recreate each directory empty when it already exists,
            removing its contents first. Only an existing *directory* is wiped;
            a non-directory still raises. Because the directory is removed and
            remade, `clean=True` makes `exist_ok` moot. **Destructive.**
            Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The created directory paths as Path objects or strings,
            depending on the value of `stringify`.

    Raises:
        ValueError: If `mode` is outside the range 0o1-0o7777
            (not checked on Windows, where the mode is ignored).
        DirectoryNotFoundError: If `root` is provided and does not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        ValueError: If `root` is provided and any of the paths are absolute.
        OSError: If `exist_ok` is False, `clean` is False, and any of the
            paths already exist.
        OSError: If any of the paths are not directories.
    """
    _validate_mode(mode)
    paths = _join_root_if_provided(paths, root)
    directories = [Path(p) for p in paths]
    for directory in directories:
        if clean and directory.is_dir():
            shutil.rmtree(directory)
        directory.mkdir(mode=mode, parents=True, exist_ok=exist_ok)
    return stringify_paths(directories) if stringify else directories


# ========================== #
#            Empty           #
# ========================== #


def dir_empty_unsafe(path: StrPath) -> bool:
    """Check if a directory is empty without existence checks."""
    with os.scandir(path) as it:
        return not any(it)


def dirs_empty_unsafe(paths: StrPaths, *, root: StrPath | None = None) -> bool:
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


def dirs_empty(paths: StrPaths, *, root: StrPath | None = None) -> bool:
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


def dir_not_empty_unsafe(path: StrPath) -> bool:
    """Check if a directory is not empty without existence checks."""
    return not dir_empty_unsafe(path)


def dirs_not_empty_unsafe(paths: StrPaths, *, root: StrPath | None = None) -> bool:
    """Check if directories are not empty without existence checks."""
    if root is not None:
        paths = [Path(root) / p for p in paths]
    return all(dir_not_empty_unsafe(p) for p in paths)


def dir_not_empty(path: StrPath) -> bool:
    """Check if a directory is not empty.

    Args:
        path: The directory path to check.

    Returns:
        True if the directory is not empty, False otherwise.

    Raises:
        DirectoryNotFoundError: If the path does not exist.
        NotADirectoryError: If the path is not a directory.
    """
    path = ensure_dir_exists(path)
    return dir_not_empty_unsafe(path)


def dirs_not_empty(paths: StrPaths, *, root: StrPath | None = None) -> bool:
    """Check if directories are not empty.

    Args:
        paths: A sequence of directory paths to check.
        root: The root directory to prepend to each path. Defaults to None.

    Returns:
        True if all directories are not empty, False otherwise.

    Raises:
        DirectoryNotFoundError: If `root` is provided and does not exist.
        DirectoryNotFoundError: If any of the paths do not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        NotADirectoryError: If any of the paths are not directories.
        ValueError: If `root` is provided and any of the paths are absolute.
    """
    paths = ensure_dirs_exist(paths, root=root)
    return all(dir_not_empty_unsafe(p) for p in paths)

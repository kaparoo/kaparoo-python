"""Create and inspect directories: `make_dir(s)`, `dir_empty(s)`, and kin."""

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
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


# ========================== #
#            Make            #
# ========================== #


# Uses `pathlib` predicates, not a single `os.lstat`: `is_dir` must follow
# symlinks, so a bare `lstat` still needs a second `stat` for a symlink
# target -- no syscall saved, and the predicates handle broken symlinks /
# Windows reparse points without decoding `st_mode`.
def _ensure_directory_target(path: Path, *, clean: bool) -> bool:
    """Validate `path` as a directory target and report whether it already exists.

    Raises `NotADirectoryError` when `path` exists but is not a directory,
    or when `clean` is requested on a symlink -- cleaning must operate on a
    real directory, never through a link (which would otherwise reach the
    link's target). A symlink to a directory is accepted only when `clean`
    is False. Returns whether `path` is an existing directory, so a caller
    can reuse the result instead of re-`stat`-ing.
    """
    exists = path.exists()
    is_dir = exists and path.is_dir()
    if (exists and not is_dir) or (clean and path.is_symlink()):
        msg = f"not a usable directory target: {path}"
        raise NotADirectoryError(msg)
    return is_dir


def _join_root_unchecked(paths: StrPaths, root: StrPath | None) -> StrPaths:
    """Prepend `root` to each path, without any existence validation."""
    return paths if root is None else [Path(root) / p for p in paths]


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
            a non-directory -- or a symlink -- still raises. Because the
            directory is removed and remade, `clean=True` makes `exist_ok`
            moot. **Destructive.** Defaults to False.
        stringify: Whether to return the path as a string. Defaults to False.

    Returns:
        The created directory path as a Path object or a string,
            depending on the value of `stringify`.

    Raises:
        ValueError: If `mode` is outside the range 0o1-0o7777
            (not checked on Windows, where the mode is ignored).
        NotADirectoryError: If the path exists but is not a directory, or
            `clean` is True and the path is a symlink.
        OSError: If `exist_ok` is False, `clean` is False, and the path
            already exists.
    """
    _validate_mode(mode)
    path = Path(path)
    is_dir = _ensure_directory_target(path, clean=clean)
    if clean and is_dir:
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
) -> list[Path]: ...


@overload
def make_dirs(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: Literal[True],
) -> list[str]: ...


@overload
def make_dirs(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: bool,
) -> list[Path] | list[str]: ...


def make_dirs(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    mode: int = 0o777,
    exist_ok: bool = False,
    clean: bool = False,
    stringify: bool = False,
) -> list[Path] | list[str]:
    """Recursively create directories.

    Args:
        paths: The directory paths to create.
        root: The root directory to prepend to each path. Defaults to None.
        mode: The mode to use when creating the directories. Defaults to 0o777.
        exist_ok: Whether to suppress OSError if any of the paths already exist.
            Defaults to False.
        clean: Whether to recreate each directory empty when it already exists,
            removing its contents first. Only an existing *directory* is wiped;
            a non-directory -- or a symlink -- still raises. Because the
            directory is removed and remade, `clean=True` makes `exist_ok`
            moot. **Destructive.** Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The created directory paths as Path objects or strings,
            depending on the value of `stringify`.

    Raises:
        ValueError: If `mode` is outside the range 0o1-0o7777
            (not checked on Windows, where the mode is ignored).
        DirectoryNotFoundError: If `root` is provided and does not exist.
        NotADirectoryError: If `root` is provided and is not a directory, if
            any path exists but is not a directory, or `clean` is True and
            any path is a symlink.
        ValueError: If `root` is provided and any of the paths are absolute.
        FileExistsError: If `exist_ok` is False, `clean` is False, and `paths`
            contains a duplicate (caught before any directory is created).
        OSError: If `exist_ok` is False, `clean` is False, and any of the
            paths already exist.

    Note:
        Every path is validated (the non-directory / symlink checks above, and
        the duplicate check under strict-create) *before* any directory is
        wiped or created, so a deterministically bad entry -- e.g. a file in
        the list, or a duplicated path under `exist_ok=False` -- fails without
        partially creating or cleaning earlier entries. Creation/cleanup is
        otherwise per-path and not transactional, so a runtime failure (a race,
        a permission error) partway through can still leave earlier entries
        created or cleaned.
    """
    _validate_mode(mode)
    paths = _join_root_if_provided(paths, root)
    directories = [Path(p) for p in paths]

    # Catch a duplicated path in the validate-first pass: with exist_ok=False
    # and no clean, the second occurrence's `mkdir` would fail only after the
    # first already created it, leaving a partial side effect. A repeat is
    # harmless (idempotent) under `exist_ok` or `clean`, so the check is scoped
    # to the strict-create case.
    if not exist_ok and not clean:
        seen: set[Path] = set()
        for directory in directories:
            if directory in seen:
                msg = f"duplicate path with exist_ok=False: {directory}"
                raise FileExistsError(msg)
            seen.add(directory)

    for directory in directories:
        _ensure_directory_target(directory, clean=clean)

    for directory in directories:
        if clean and directory.is_dir():
            shutil.rmtree(directory)
        directory.mkdir(mode=mode, parents=True, exist_ok=exist_ok)

    return stringify_paths(directories) if stringify else directories


# ========================== #
#            Empty           #
# ========================== #


def dir_empty_unsafe(path: StrPath) -> bool:
    """Test whether a directory is empty, skipping the existence check.

    The caller must guarantee `path` is an existing directory; otherwise the
    underlying `os.scandir` raises (`FileNotFoundError`, `NotADirectoryError`).
    """
    with os.scandir(path) as it:
        return not any(it)


def dirs_empty_unsafe(paths: StrPaths, *, root: StrPath | None = None) -> bool:
    """Test whether directories are empty, skipping existence checks.

    Each path carries the same caller obligation as `dir_empty_unsafe`.
    """
    return all(dir_empty_unsafe(p) for p in _join_root_unchecked(paths, root))


def dir_empty(path: StrPath) -> bool:
    """Test whether a directory is empty.

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
    """Test whether directories are empty.

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
    """Test whether a directory is not empty, skipping the existence check.

    Same caller obligation as `dir_empty_unsafe`.
    """
    return not dir_empty_unsafe(path)


def dirs_not_empty_unsafe(paths: StrPaths, *, root: StrPath | None = None) -> bool:
    """Test whether directories are not empty, skipping existence checks.

    Each path carries the same caller obligation as `dir_empty_unsafe`.
    """
    return all(dir_not_empty_unsafe(p) for p in _join_root_unchecked(paths, root))


def dir_not_empty(path: StrPath) -> bool:
    """Test whether a directory is not empty.

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
    """Test whether directories are not empty.

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

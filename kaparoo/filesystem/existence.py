from __future__ import annotations

__all__ = (
    # single
    "path_exists",
    "file_exists",
    "dir_exists",
    "ensure_path_exists",
    "ensure_file_exists",
    "ensure_dir_exists",
    # multiple
    "paths_exist",
    "files_exist",
    "dirs_exist",
    "ensure_paths_exist",
    "ensure_files_exist",
    "ensure_dirs_exist",
)

import os
from pathlib import Path
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.exceptions import DirectoryNotFoundError, NotAFileError
from kaparoo.filesystem.utils import prepend_paths, stringify_path, stringify_paths

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


# ========================== #
#           Single           #
# ========================== #


def path_exists(path: StrPath) -> bool:
    """Test whether a given path exists."""
    return os.path.exists(path)


def file_exists(path: StrPath) -> bool:
    """Test whether a given path is an existing file."""
    return os.path.isfile(path)


def dir_exists(path: StrPath) -> bool:
    """Test whether a given path is an existing directory."""
    return os.path.isdir(path)


@overload
def ensure_path_exists(path: StrPath, *, stringify: Literal[False] = False) -> Path:
    ...


@overload
def ensure_path_exists(path: StrPath, *, stringify: Literal[True]) -> str:
    ...


@overload
def ensure_path_exists(path: StrPath, *, stringify: bool) -> Path | str:
    ...


def ensure_path_exists(path: StrPath, *, stringify: bool = False) -> Path | str:
    """Check if a given path exists and return it as a Path object.

    Args:
        path: The path to check for existence.
        stringify: Whether to return the path as a string. Defaults to False.

    Returns:
        The path as a Path object or a string, depending on the value of `stringify`.

    Raises:
        FileNotFoundError: If the path does not exist.
    """
    if not path_exists(path := Path(path)):
        raise FileNotFoundError(f"no such path: {path}")
    return stringify_path(path) if stringify else path


@overload
def ensure_file_exists(path: StrPath, *, stringify: Literal[False] = False) -> Path:
    ...


@overload
def ensure_file_exists(path: StrPath, *, stringify: Literal[True]) -> str:
    ...


@overload
def ensure_file_exists(path: StrPath, *, stringify: bool) -> Path | str:
    ...


def ensure_file_exists(path: StrPath, *, stringify: bool = False) -> Path | str:
    """Check if a given path exists and is a file, and return it as a Path object.

    Args:
        path: The file path to check for existence.
        stringify: Whether to return the path as a string. Defaults to False.

    Returns:
        The path as a Path object or a string, depending on the value of `stringify`.

    Raises:
        FileNotFoundError: If the path does not exist.
        NotAFileError: If the path exists but is not a file.
    """
    if not path_exists(path := Path(path)):
        raise FileNotFoundError(f"no such file: {path}")
    if not path.is_file():
        raise NotAFileError(f"not a file: {path}")
    return stringify_path(path) if stringify else path


@overload
def ensure_dir_exists(
    path: StrPath, *, make: bool | int = False, stringify: Literal[False] = False
) -> Path:
    ...


@overload
def ensure_dir_exists(
    path: StrPath, *, make: bool | int = False, stringify: Literal[True]
) -> str:
    ...


@overload
def ensure_dir_exists(
    path: StrPath, *, make: bool | int = False, stringify: bool
) -> Path | str:
    ...


def ensure_dir_exists(
    path: StrPath, *, make: bool | int = False, stringify: bool = False
) -> Path | str:
    """Check if a given path exists and is a directory, and return it as a Path object.

    Args:
        path: The directory path to check for existence.
        make: Whether to create the directory with mode `0o777` if it does not exist.
            If an integer is provided, use it as the octal mode. Defaults to False.
        stringify: Whether to return the path as a string. Defaults to False.

    Returns:
        The path as a Path object or a string, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If the path does not exist and `make` is False.
        NotADirectoryError: If the path exists but is not a directory.
    """
    if not path_exists(path := Path(path)):
        if make is False:
            raise DirectoryNotFoundError(f"no such directory: {path}")
        path.mkdir(mode=0o777 if make is True else make, parents=True)
    if not path.is_dir():
        raise NotADirectoryError(f"not a directory: {path}")
    return stringify_path(path) if stringify else path


# ========================== #
#          Multiple          #
# ========================== #


def _join_root_if_provided(paths: StrPaths, root: StrPath | None) -> StrPaths:
    if root is not None:
        root = ensure_dir_exists(root)
        paths = prepend_paths(paths, root)
    return paths


def paths_exist(paths: StrPaths, *, root: StrPath | None = None) -> bool:
    """Test whether all of the given paths exist.

    Args:
        paths: The paths to check for existence.
        root: The root directory to prepend to each path. Defaults to None.

    Returns:
        True if all paths exist, False otherwise.

    Raises:
        DirectoryNotFoundError: If `root` is provided and does not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        ValueError: If `root` is provided and any of the paths are absolute.
    """
    paths = _join_root_if_provided(paths, root)
    return all(path_exists(p) for p in paths)


def files_exist(paths: StrPaths, *, root: StrPath | None = None) -> bool:
    """Test whether all of the given paths exist and are files.

    Args:
        paths: The file paths to check for existence.
        root: The root directory to prepend to each path. Defaults to None.

    Returns:
        True if all paths exist and are files, False otherwise.

    Raises:
        DirectoryNotFoundError: If `root` is provided and does not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        ValueError: If `root` is provided and any of the paths are absolute.
    """
    paths = _join_root_if_provided(paths, root)
    return all(file_exists(p) for p in paths)


def dirs_exist(paths: StrPaths, *, root: StrPath | None = None) -> bool:
    """Test whether all of the given paths exist and are directories.

    Args:
        paths: The directory paths to check for existence.
        root: The root directory to prepend to each path. Defaults to None.

    Returns:
        True if all paths exist and are directories, False otherwise.

    Raises:
        DirectoryNotFoundError: If `root` is provided and does not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        ValueError: If `root` is provided and any of the paths are absolute.
    """
    paths = _join_root_if_provided(paths, root)
    return all(dir_exists(p) for p in paths)


@overload
def ensure_paths_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: Literal[False] = False
) -> Sequence[Path]:
    ...


@overload
def ensure_paths_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: Literal[True]
) -> Sequence[str]:
    ...


@overload
def ensure_paths_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: bool
) -> Sequence[Path] | Sequence[str]:
    ...


def ensure_paths_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: bool = False
) -> Sequence[Path] | Sequence[str]:
    """Check if all of the given paths exist and return them as Path objects.

    Args:
        paths: The paths to check for existence.
        root: The root directory to prepend to each path. Defaults to None.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The paths as Path objects or strings, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If `root` is provided and does not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        ValueError: If `root` is provided and any of the paths are absolute.
        FileNotFoundError: If any of the paths do not exist.
    """
    paths = _join_root_if_provided(paths, root)
    paths = [ensure_path_exists(p) for p in paths]
    return stringify_paths(paths) if stringify else paths


@overload
def ensure_files_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: Literal[False] = False
) -> Sequence[Path]:
    ...


@overload
def ensure_files_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: Literal[True]
) -> Sequence[str]:
    ...


@overload
def ensure_files_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: bool
) -> Sequence[Path] | Sequence[str]:
    ...


def ensure_files_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: bool = False
) -> Sequence[Path] | Sequence[str]:
    """Check if all of the given paths exist and are files, and return them as Path objects.

    Args:
        paths: The file paths to check for existence.
        root: The root directory to prepend to each path. Defaults to None.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The paths as Path objects or strings, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If `root` is provided and does not exist.
        NotADirectoryError: If `root` is provided and is not a directory.
        ValueError: If `root` is provided and any of the paths are absolute.
        FileNotFoundError: If any of the paths do not exist.
        NotAFileError: If any of the paths exist but are not files.
    """
    paths = _join_root_if_provided(paths, root)
    paths = [ensure_file_exists(p) for p in paths]
    return stringify_paths(paths) if stringify else paths


@overload
def ensure_dirs_exist(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    make: bool | int = False,
    stringify: Literal[False] = False,
) -> Sequence[Path]:
    ...


@overload
def ensure_dirs_exist(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    make: bool | int = False,
    stringify: Literal[True],
) -> Sequence[str]:
    ...


@overload
def ensure_dirs_exist(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    make: bool | int = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]:
    ...


def ensure_dirs_exist(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    make: bool | int = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Check if all of the given paths exist and are directories, and return them as Path objects.

    Args:
        paths: The directory paths to check for existence.
        root: The root directory to prepend to each path. Defaults to None.
        make: Whether to create the directories with mode `0o777` if they do not exist.
            If an integer is provided, use it as the octal mode. Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The paths as Path objects or strings, depending on the value of `stringify`.

    Raises:
        DirectoryNotFoundError: If `root` is provided and does not exist.
        DirectoryNotFoundError: If any of the paths do not exist and `make` is False.
        NotADirectoryError: If `root` is provided and is not a directory.
        NotADirectoryError: If any of the paths exist but are not directories.
        ValueError: If `root` is provided and any of the paths are absolute.
    """
    paths = _join_root_if_provided(paths, root)
    paths = [ensure_dir_exists(p, make=make) for p in paths]
    return stringify_paths(paths) if stringify else paths

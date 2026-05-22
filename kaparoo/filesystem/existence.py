from __future__ import annotations

__all__ = (
    "dir_exists",
    "dirs_exist",
    "ensure_dir_exists",
    "ensure_dirs_exist",
    "ensure_file_exists",
    "ensure_files_exist",
    "ensure_path_exists",
    "ensure_paths_exist",
    "file_exists",
    "files_exist",
    "path_exists",
    "paths_exist",
)

import platform
from pathlib import Path
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.exceptions import DirectoryNotFoundError, NotAFileError
from kaparoo.filesystem.utils import stringify_path, stringify_paths, wrap_paths

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


# ========================== #
#           Single           #
# ========================== #


def path_exists(path: StrPath) -> bool:
    """Test whether a given path exists."""
    return Path(path).exists()


def file_exists(path: StrPath) -> bool:
    """Test whether a given path is an existing file."""
    return Path(path).is_file()


def dir_exists(path: StrPath) -> bool:
    """Test whether a given path is an existing directory."""
    return Path(path).is_dir()


@overload
def ensure_path_exists(path: StrPath, *, stringify: Literal[False] = False) -> Path: ...


@overload
def ensure_path_exists(path: StrPath, *, stringify: Literal[True]) -> str: ...


@overload
def ensure_path_exists(path: StrPath, *, stringify: bool) -> Path | str: ...


def ensure_path_exists(path: StrPath, *, stringify: bool = False) -> Path | str:
    """Check if a given path exists and return it.

    Args:
        path: The path to check for existence.
        stringify: Whether to return the path as a string. Defaults to False.

    Returns:
        The path as a Path object or a string, depending on the value of `stringify`.

    Raises:
        FileNotFoundError: If the path does not exist.
    """
    if not path_exists(path := Path(path)):
        msg = f"no such path: {path}"
        raise FileNotFoundError(msg)
    return stringify_path(path) if stringify else path


@overload
def ensure_file_exists(path: StrPath, *, stringify: Literal[False] = False) -> Path: ...


@overload
def ensure_file_exists(path: StrPath, *, stringify: Literal[True]) -> str: ...


@overload
def ensure_file_exists(path: StrPath, *, stringify: bool) -> Path | str: ...


def ensure_file_exists(path: StrPath, *, stringify: bool = False) -> Path | str:
    """Check if a given path exists and is a file, and return it.

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
        msg = f"no such file: {path}"
        raise FileNotFoundError(msg)
    if not path.is_file():
        msg = f"not a file: {path}"
        raise NotAFileError(msg)
    return stringify_path(path) if stringify else path


def _validate_mode(mode: int) -> None:
    """Reject directory modes outside 0o1-0o7777 (skipped on Windows)."""
    if platform.system() != "Windows" and not (0 < mode <= 0o7777):
        msg = f"invalid directory mode: {mode:#o}"
        raise ValueError(msg)


@overload
def ensure_dir_exists(
    path: StrPath, *, make: bool | int = False, stringify: Literal[False] = False
) -> Path: ...


@overload
def ensure_dir_exists(
    path: StrPath, *, make: bool | int = False, stringify: Literal[True]
) -> str: ...


@overload
def ensure_dir_exists(
    path: StrPath, *, make: bool | int = False, stringify: bool
) -> Path | str: ...


def ensure_dir_exists(
    path: StrPath, *, make: bool | int = False, stringify: bool = False
) -> Path | str:
    """Check if a given path exists and is a directory, and return it.

    Args:
        path: The directory path to check for existence.
        make: Whether to create the directory with mode `0o777` if it does not exist.
            If an integer is provided, use it as the octal mode. Defaults to False.
        stringify: Whether to return the path as a string. Defaults to False.

    Returns:
        The path as a Path object or a string, depending on the value of `stringify`.

    Raises:
        ValueError: If `make` is an int outside the range 0o1-0o7777
            (not checked on Windows, where the mode is ignored).
        DirectoryNotFoundError: If the path does not exist and `make` is False.
        NotADirectoryError: If the path exists but is not a directory.
    """
    if not isinstance(make, bool):
        _validate_mode(make)
    if not path_exists(path := Path(path)):
        if make is False:
            msg = f"no such directory: {path}"
            raise DirectoryNotFoundError(msg)
        path.mkdir(mode=0o777 if make is True else make, parents=True)
    if not path.is_dir():
        msg = f"not a directory: {path}"
        raise NotADirectoryError(msg)
    return stringify_path(path) if stringify else path


# ========================== #
#          Multiple          #
# ========================== #


def _join_root_if_provided(paths: StrPaths, root: StrPath | None) -> StrPaths:
    """Prepend `root` to each of `paths` if `root` is provided."""
    if root is not None:
        root = ensure_dir_exists(root)
        paths = wrap_paths(paths, prepend=root)
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
) -> Sequence[Path]: ...


@overload
def ensure_paths_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: Literal[True]
) -> Sequence[str]: ...


@overload
def ensure_paths_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: bool
) -> Sequence[Path] | Sequence[str]: ...


def ensure_paths_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: bool = False
) -> Sequence[Path] | Sequence[str]:
    """Check if all of the given paths exist and return them.

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
) -> Sequence[Path]: ...


@overload
def ensure_files_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: Literal[True]
) -> Sequence[str]: ...


@overload
def ensure_files_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: bool
) -> Sequence[Path] | Sequence[str]: ...


def ensure_files_exist(
    paths: StrPaths, *, root: StrPath | None = None, stringify: bool = False
) -> Sequence[Path] | Sequence[str]:
    """Check if all of the given paths exist and are files, and return them.

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
) -> Sequence[Path]: ...


@overload
def ensure_dirs_exist(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    make: bool | int = False,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def ensure_dirs_exist(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    make: bool | int = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def ensure_dirs_exist(
    paths: StrPaths,
    *,
    root: StrPath | None = None,
    make: bool | int = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Check if all of the given paths exist and are directories, and return them.

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
        ValueError: If `make` is an int outside the range 0o1-0o7777.
    """
    if not isinstance(make, bool):
        _validate_mode(make)
    paths = _join_root_if_provided(paths, root)
    paths = [ensure_dir_exists(p, make=make) for p in paths]
    return stringify_paths(paths) if stringify else paths

from __future__ import annotations

__all__ = (
    "path_exists",
    "file_exists",
    "dir_exists",
    "ensure_path_exists",
    "ensure_file_exists",
    "ensure_dir_exists",
)

import os
from pathlib import Path
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.exceptions import DirectoryNotFoundError, NotAFileError
from kaparoo.filesystem.utils import stringify_path

if TYPE_CHECKING:
    from typing import Literal

    from kaparoo.filesystem.types import StrPath


# ========================== #
#           Single           #
# ========================== #


def path_exists(path: StrPath) -> bool:
    """Test whether a path exists."""
    return os.path.exists(path)


def file_exists(path: StrPath) -> bool:
    """Test whether a path is an existing file."""
    return os.path.isfile(path)


def dir_exists(path: StrPath) -> bool:
    """Test whether a path is an existing directory."""
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
        DirectoryNotFoundError: If the path does not exist.
        NotADirectoryError: If the path exists but is not a directory.
    """
    if not path_exists(path := Path(path)):
        if make is False:
            raise DirectoryNotFoundError(f"no such directory: {path}")
        path.mkdir(mode=0o777 if make is True else make, parents=True)
    if not path.is_dir():
        raise NotADirectoryError(f"not a directory: {path}")
    return stringify_path(path) if stringify else path

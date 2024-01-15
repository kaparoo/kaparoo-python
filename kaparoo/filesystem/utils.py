from __future__ import annotations

__all__ = ("stringify_path", "stringify_paths", "prepend_path", "prepend_paths")

import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


def stringify_path(path: StrPath, after: StrPath | None = None) -> str:
    r"""Convert a path to a string and optionally make it relative.

    Args:
        path: The path to be converted to a string. In Windows platform,
            all "\\" will be replaced with "/".
        after: The base path to make the `path` relative to. If provided,
            returns only the string representation of `path` after `after`.
            Defaults to None.

    Returns:
        The string representation of the `path`.

    Raises:
        ValueError: If `path` does not start with `after`.
    """
    if after is not None:
        path = Path(path).relative_to(after)  # raise ValueError if not possible
    path = os.fspath(path)
    if platform.system() == "Windows":
        path = path.replace("\\", "/")
    return path


def stringify_paths(paths: StrPaths, after: StrPath | None = None) -> Sequence[str]:
    r"""Convert a sequence of paths to strings and optionally make them relative.

    Args:
        paths: The sequence of paths to be converted to strings.
            In Windows platform, all "\\" will be replaced with "/".
        after: The base path to make all of `paths` relative to. If provided,
            returns only the string representation of each path in `paths`
            after `after`. Defaults to None.

    Returns:
        The sequence of string representations of the `paths`.

    Raises:
        ValueError: If any of `paths` does not start with `after`.
    """
    return [stringify_path(path, after) for path in paths]


@overload
def prepend_path(
    path: StrPath, base: StrPath, *, stringify: Literal[False] = False
) -> Path:
    ...


@overload
def prepend_path(path: StrPath, base: StrPath, *, stringify: Literal[True]) -> str:
    ...


@overload
def prepend_path(path: StrPath, base: StrPath, *, stringify: bool) -> Path | str:
    ...


def prepend_path(
    path: StrPath, base: StrPath, *, stringify: bool = False
) -> Path | str:
    """Prepend a base path to a relative path.

    Args:
        path: The relative path to which the base path will be prepended.
        base: The base path to prepend to the provided relative path.
        stringify: Whether to return the prepended path as a string. Defaults to False.

    Returns:
        A Path object or a string with the base path prepended,
            depending on the value of `stringify`.

    Raises:
        ValueError: If the provided path is an absolute path.
    """
    if os.path.isabs(path):
        raise ValueError(f"cannot prepend to absolute path: {path}")
    path = Path(base, path)
    return stringify_path(path) if stringify else path


@overload
def prepend_paths(
    paths: StrPaths, base: StrPath, *, stringify: Literal[False] = False
) -> Sequence[Path]:
    ...


@overload
def prepend_paths(
    paths: StrPaths, base: StrPath, *, stringify: Literal[True]
) -> Sequence[str]:
    ...


@overload
def prepend_paths(
    paths: StrPaths, base: StrPath, *, stringify: bool
) -> Sequence[Path] | Sequence[str]:
    ...


def prepend_paths(
    paths: StrPaths, base: StrPath, *, stringify: bool = False
) -> Sequence[Path] | Sequence[str]:
    """Prepend a base path to a sequence of relative paths.

    Args:
        paths: A sequence of relative paths to which the base path will be prepended.
        base: The base path to prepend to each of the provided relative paths
        stringify: Whether to return the prepended paths as strings. Defaults to False.

    Returns:
        A sequence of Path objects or strings with the base path prepended,
            depending on the value of `stringify`.

    Raises:
        ValueError: If any of the provided paths is an absolute path.
    """
    paths = [prepend_path(path, base) for path in paths]
    return stringify_paths(paths) if stringify else paths

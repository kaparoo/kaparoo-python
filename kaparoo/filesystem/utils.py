from __future__ import annotations

__all__ = ("prepend_path", "prepend_paths", "stringify_path", "stringify_paths")

import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


def _stringify_path(
    path: StrPath,
    after: StrPath | None,
    tail: tuple[str, ...],
    *,
    is_windows: bool,
) -> str:
    """Core of `stringify_path` taking pre-computed loop-invariant inputs."""
    if after is not None or tail:
        path = Path(path)
        if after is not None:
            path = path.relative_to(after)  # raise ValueError if not possible
        if tail:
            if path.parts[-len(tail) :] != tail:
                msg = f"path {path} does not end with {Path(*tail)}"
                raise ValueError(msg)
            path = Path(*path.parts[: -len(tail)])
    text = os.fspath(path)
    if is_windows:
        text = text.replace("\\", "/")
    return text


def stringify_path(
    path: StrPath, after: StrPath | None = None, before: StrPath | None = None
) -> str:
    r"""Convert a path to a string and optionally trim shared head/tail parts.

    Args:
        path: The path to be converted to a string. In Windows platform,
            all "\\" will be replaced with "/".
        after: The leading base path to make `path` relative to. If provided,
            returns only the part of `path` after `after`. Defaults to None.
        before: The trailing path to trim from `path`. If provided, returns
            only the part of `path` before `before`. Defaults to None.

    Returns:
        The string representation of the `path`.

    Raises:
        ValueError: If `path` does not start with `after`,
            or does not end with `before`.
    """
    tail = Path(before).parts if before is not None else ()
    is_windows = platform.system() == "Windows"
    return _stringify_path(path, after, tail, is_windows=is_windows)


def stringify_paths(
    paths: StrPaths, after: StrPath | None = None, before: StrPath | None = None
) -> Sequence[str]:
    r"""Convert a sequence of paths to strings and optionally trim shared parts.

    Args:
        paths: The sequence of paths to be converted to strings.
            In Windows platform, all "\\" will be replaced with "/".
        after: The leading base path to make each path relative to. If provided,
            returns only the part of each path after `after`. Defaults to None.
        before: The trailing path to trim from each path. If provided, returns
            only the part of each path before `before`. Defaults to None.

    Returns:
        The sequence of string representations of the `paths`.

    Raises:
        ValueError: If any of `paths` does not start with `after`,
            or does not end with `before`.
    """
    tail = Path(before).parts if before is not None else ()
    is_windows = platform.system() == "Windows"
    return [_stringify_path(path, after, tail, is_windows=is_windows) for path in paths]


@overload
def prepend_path(
    path: StrPath, base: StrPath, *, stringify: Literal[False] = False
) -> Path: ...


@overload
def prepend_path(path: StrPath, base: StrPath, *, stringify: Literal[True]) -> str: ...


@overload
def prepend_path(path: StrPath, base: StrPath, *, stringify: bool) -> Path | str: ...


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
    if os.path.isabs(path):  # noqa: PTH117
        msg = f"cannot prepend to absolute path: {path}"
        raise ValueError(msg)
    path = Path(base, path)
    return stringify_path(path) if stringify else path


@overload
def prepend_paths(
    paths: StrPaths, base: StrPath, *, stringify: Literal[False] = False
) -> Sequence[Path]: ...


@overload
def prepend_paths(
    paths: StrPaths, base: StrPath, *, stringify: Literal[True]
) -> Sequence[str]: ...


@overload
def prepend_paths(
    paths: StrPaths, base: StrPath, *, stringify: bool
) -> Sequence[Path] | Sequence[str]: ...


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

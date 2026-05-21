from __future__ import annotations

__all__ = ("stringify_path", "stringify_paths", "wrap_path", "wrap_paths")

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
def wrap_path(
    path: StrPath,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[False] = False,
) -> Path: ...


@overload
def wrap_path(
    path: StrPath,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[True],
) -> str: ...


@overload
def wrap_path(
    path: StrPath,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool,
) -> Path | str: ...


def wrap_path(
    path: StrPath,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool = False,
) -> Path | str:
    """Wrap a path with an optional leading and/or trailing path.

    Args:
        path: The path to wrap.
        prepend: A path to attach in front of `path`. Defaults to None.
        append: A relative path to attach after `path`. Defaults to None.
        stringify: Whether to return the result as a string. Defaults to False.

    Returns:
        A Path object or a string, depending on the value of `stringify`.

    Raises:
        ValueError: If `prepend` is given and `path` is an absolute path.
        ValueError: If `append` is given and is an absolute path.
    """
    if prepend is not None and os.path.isabs(path):  # noqa: PTH117
        msg = f"cannot prepend to absolute path: {path}"
        raise ValueError(msg)
    if append is not None and os.path.isabs(append):  # noqa: PTH117
        msg = f"cannot append an absolute path: {append}"
        raise ValueError(msg)
    result = Path(path) if prepend is None else Path(prepend, path)
    if append is not None:
        result = result / append
    return stringify_path(result) if stringify else result


@overload
def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Wrap a sequence of paths with an optional leading and/or trailing path.

    Args:
        paths: The sequence of paths to wrap.
        prepend: A path to attach in front of each path. Defaults to None.
        append: A relative path to attach after each path. Defaults to None.
        stringify: Whether to return the results as strings. Defaults to False.

    Returns:
        A sequence of Path objects or strings, depending on the value of
            `stringify`.

    Raises:
        ValueError: If `prepend` is given and any path is an absolute path.
        ValueError: If `append` is given and is an absolute path.
    """
    paths = [wrap_path(path, prepend=prepend, append=append) for path in paths]
    return stringify_paths(paths) if stringify else paths

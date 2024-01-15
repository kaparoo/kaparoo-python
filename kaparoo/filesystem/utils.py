from __future__ import annotations

__all__ = ("stringify_path", "stringify_paths")

import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

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
    r"""Convert multiple paths to strings and optionally make them relative.

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

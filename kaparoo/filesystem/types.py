"""Shared filesystem type aliases (`StrPath`, `StrPaths`)."""

from __future__ import annotations

__all__ = ("StrPath", "StrPaths")

from collections.abc import Sequence
from os import PathLike

type StrPath = str | PathLike[str]
type StrPaths = Sequence[StrPath]

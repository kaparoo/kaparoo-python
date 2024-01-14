__all__ = ("StrPath", "StrPaths")

from collections.abc import Sequence
from os import PathLike
from typing import TypeAlias

StrPath: TypeAlias = str | PathLike[str]
StrPaths: TypeAlias = Sequence[StrPath]

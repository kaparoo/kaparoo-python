from __future__ import annotations

__all__ = ("DataFolder",)

from abc import abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.existence import ensure_dir_exists
from kaparoo.utils.types import T_co

if TYPE_CHECKING:
    from typing import Self

    from kaparoo.filesystem.types import StrPath, StrPaths


class DataFolder(Sequence[T_co]):
    def __init__(self: Self, path: StrPath) -> None:
        self.path = ensure_dir_exists(path)
        self.files = self.list_files(self.path)

    def __len__(self: Self) -> int:
        return len(self.files)

    @overload
    def __getitem__(self: Self, index: int, /) -> T_co:
        pass

    @overload
    def __getitem__(self: Self, index: slice, /) -> Sequence[T_co]:
        pass

    def __getitem__(self: Self, index: int | slice, /) -> T_co | Sequence[T_co]:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return self.parse_files(range(start, stop, step))
        return self.parse_file(index)

    @abstractmethod
    def parse_file(self: Self, index: int) -> T_co:
        raise NotImplementedError

    def parse_files(self: Self, indices: Sequence[int]) -> Sequence[T_co]:
        return [self.parse_file(i) for i in indices]

    @classmethod
    @abstractmethod
    def list_files(cls: type[Self], path: StrPath) -> StrPaths:
        raise NotImplementedError

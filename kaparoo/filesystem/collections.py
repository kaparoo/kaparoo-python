from __future__ import annotations

__all__ = ("DataSequence", "DataFilesFolder", "MultiDataFile")

from abc import abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.existence import ensure_dir_exists, ensure_file_exists
from kaparoo.utils.types import T_co

if TYPE_CHECKING:
    from typing import Self

    from kaparoo.filesystem.types import StrPath


class DataSequence(Sequence[T_co]):
    @abstractmethod
    def __init__(self: Self, path: StrPath) -> None:
        raise NotImplementedError

    @abstractmethod
    def __len__(self: Self) -> int:
        raise NotImplementedError

    @overload
    def __getitem__(self: Self, index: int, /) -> T_co:
        pass

    @overload
    def __getitem__(self: Self, index: slice, /) -> Sequence[T_co]:
        pass

    def __getitem__(self: Self, index: int | slice, /) -> T_co | Sequence[T_co]:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return self.by_indices(range(start, stop, step))
        return self.by_index(index)

    @abstractmethod
    def by_index(self: Self, index: int) -> T_co:
        raise NotImplementedError

    def by_indices(self: Self, indices: Sequence[int]) -> Sequence[T_co]:
        return [self.by_index(index) for index in indices]


class DataFilesFolder(DataSequence):
    def __init__(self: Self, path: StrPath) -> None:
        self.path = ensure_dir_exists(path)


class MultiDataFile(DataSequence):
    def __init__(self: Self, path: StrPath) -> None:
        self.path = ensure_file_exists(path)

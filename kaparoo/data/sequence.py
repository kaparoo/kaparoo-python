from __future__ import annotations

__all__ = ("DataSequence",)

from abc import abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from kaparoo.filesystem.types import StrPath


class DataSequence[T](Sequence[T]):
    @abstractmethod
    def __init__(self, path: StrPath) -> None:
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        raise NotImplementedError

    @overload
    def __getitem__(self, index: int, /) -> T: ...

    @overload
    def __getitem__(self, index: slice, /) -> Sequence[T]: ...

    def __getitem__(self, index: int | slice, /) -> T | Sequence[T]:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return self.by_indices(range(start, stop, step))
        return self.by_index(index)

    @abstractmethod
    def by_index(self, index: int) -> T:
        raise NotImplementedError

    def by_indices(self, indices: Sequence[int]) -> Sequence[T]:
        return [self.by_index(index) for index in indices]

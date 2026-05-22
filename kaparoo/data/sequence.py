from __future__ import annotations

__all__ = ("DataSequence",)

from abc import abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from typing import Self

    from kaparoo.filesystem.types import StrPath


class DataSequence[T](Sequence[T]):
    @abstractmethod
    def __init__(self: Self, path: StrPath) -> None:
        raise NotImplementedError

    @abstractmethod
    def __len__(self: Self) -> int:
        raise NotImplementedError

    @overload
    def __getitem__(self: Self, index: int, /) -> T: ...

    @overload
    def __getitem__(self: Self, index: slice, /) -> Sequence[T]: ...

    def __getitem__(self: Self, index: int | slice, /) -> T | Sequence[T]:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return self.by_indices(range(start, stop, step))
        return self.by_index(index)

    @abstractmethod
    def by_index(self: Self, index: int) -> T:
        raise NotImplementedError

    def by_indices(self: Self, indices: Sequence[int]) -> Sequence[T]:
        return [self.by_index(index) for index in indices]

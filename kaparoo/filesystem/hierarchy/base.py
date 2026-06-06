from __future__ import annotations

__all__ = ("Node",)

from abc import ABC, abstractmethod


class Node(ABC):
    """A member of a hierarchy -- anything that can sit in a directory.

    The shared base of `Entry` (named filesystem nodes) and `Group`
    (unnamed constraint nodes). Nodes are immutable value objects: equal
    when they are the same concrete type with equal `_key`s, and hashable
    on the same basis.
    """

    __slots__ = ()

    @abstractmethod
    def _key(self) -> tuple[object, ...]:
        """Return the fields that define this node's identity."""
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Node) and type(self) is type(other):
            return self._key() == other._key()
        return NotImplemented

    def __hash__(self) -> int:
        return hash((type(self), self._key()))

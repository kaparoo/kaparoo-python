from __future__ import annotations

__all__ = (
    "Directory",
    "Entry",
    "File",
)

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from kaparoo.filesystem.hierarchy.patterns import Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

    from kaparoo.filters import Filter


def _as_filter(name: str | Filter) -> Filter:
    """Coerce a bare name into a `Literal`; pass a filter through."""
    return Literal(name) if isinstance(name, str) else name


class Entry(ABC):
    """A node in a filesystem hierarchy: a `File` or a `Directory`.

    Every entry carries a `name` filter. A bare `str` passed to a
    constructor is sugar for `Literal(name)`. Entries are immutable value
    objects -- equal by type, name, and (for a directory) its children --
    hashable, with a `repr` that round-trips their fields.

    A node's `name` is any `kaparoo.filters.Filter`, so the full filter
    DSL (`Glob`, `Regex`, `And` / `Or` / `Not`, ...) describes which
    siblings a node matches. Names that are also `Expandable` (`Literal`,
    `Template`) can additionally be enumerated -- the basis for
    scaffolding.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str | Filter) -> None:
        self._name = _as_filter(name)

    @property
    def name(self) -> Filter:
        """The filter naming this entry (one or many siblings)."""
        return self._name

    @abstractmethod
    def _key(self) -> tuple[object, ...]:
        """Return the fields that define this entry's identity."""
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Entry) and type(self) is type(other):
            return self._key() == other._key()
        return NotImplemented

    def __hash__(self) -> int:
        return hash((type(self), self._key()))

    def __repr__(self) -> str:
        inner = ", ".join(repr(part) for part in self._key())
        return f"{type(self).__name__}({inner})"


class File(Entry):
    """A leaf entry: a file named by its `name` filter."""

    __slots__ = ()

    def _key(self) -> tuple[object, ...]:
        return (self._name,)


class Directory(Entry):
    """An internal entry: a directory named by `name`, holding `children`.

    `children` is materialized to a tuple at construction and preserves
    insertion order. When `name` matches many sibling directories,
    `children` describes the shape shared by every one of them.
    """

    __slots__ = ("_children",)

    def __init__(self, name: str | Filter, children: Iterable[Entry] = ()) -> None:
        super().__init__(name)
        self._children = tuple(children)

    @property
    def children(self) -> tuple[Entry, ...]:
        """The contained entries, in insertion order."""
        return self._children

    def _key(self) -> tuple[object, ...]:
        return (self._name, self._children)

from __future__ import annotations

__all__ = (
    "Directory",
    "Entry",
    "File",
)

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from kaparoo.filesystem.hierarchy.patterns import Literal, OneOf
from kaparoo.filters import Filter

if TYPE_CHECKING:
    from collections.abc import Iterable


def _as_filter(name: str | list[str] | Filter) -> Filter:
    """Coerce a bare name into a pattern; pass a filter through.

    A `Filter` is returned unchanged, a `str` becomes a `Literal`, and a
    `list[str]` becomes a `OneOf` (the shared-structure shorthand).
    """
    if isinstance(name, Filter):
        return name
    if isinstance(name, str):
        return Literal(name)
    return OneOf(name)


def _depth_suffix(depth: int | None) -> str:
    """Render the `depth=` part of a `repr`, omitted when it is the default."""
    return "" if depth == 1 else f", depth={depth!r}"


class Entry(ABC):
    """A node in a filesystem hierarchy: a `File` or a `Directory`.

    Every entry carries a `name` filter. As constructor sugar, a bare
    `str` becomes a `Literal` and a `list[str]` becomes a `OneOf` -- the
    latter lets one node stand for several literally-named siblings that
    share a structure (`Directory(["train", "val"], layout)`). Entries are
    immutable value objects -- equal by type, name, `depth`, and (for a
    directory) its children -- hashable, with a `repr` that round-trips
    their fields.

    A node's `name` is any `kaparoo.filters.Filter`, so the full filter
    DSL (`Glob`, `Regex`, `And` / `Or` / `Not`, ...) describes which
    siblings a node matches. Names that are also `Expandable` (`Literal`,
    `OneOf`, `Template`) can additionally be enumerated -- the basis for
    scaffolding.

    `depth` is how far below its parent the entry sits, defaulting to 1
    (a direct child). A larger `depth` places the entry that many levels
    down past intermediate directories of unknown name; `depth=None` means
    any depth (one or more levels), the tree-level analogue of a `**`
    glob. Because the intermediate names are unknown, an entry with
    `depth != 1` describes structure for *matching*, not scaffolding.
    This is representation only -- the matching that consumes `depth` is
    not implemented yet.

    Args:
        name: The entry's name (a filter, or `str` / `list[str]` sugar).
        depth: Levels below the parent, `>= 1`, or `None` for any depth.
            Defaults to 1.

    Raises:
        ValueError: If `depth` is an integer less than 1.
    """

    __slots__ = ("_depth", "_name")

    def __init__(
        self,
        name: str | list[str] | Filter,
        *,
        depth: int | None = 1,
    ) -> None:
        if depth is not None and depth < 1:
            msg = f"depth must be None or a positive integer, got {depth!r}"
            raise ValueError(msg)
        self._name = _as_filter(name)
        self._depth = depth

    @property
    def name(self) -> Filter:
        """The filter naming this entry (one or many siblings)."""
        return self._name

    @property
    def depth(self) -> int | None:
        """Levels below the parent (`1` = direct child; `None` = any depth)."""
        return self._depth

    @abstractmethod
    def _fields(self) -> tuple[object, ...]:
        """Return the identity fields shown in `repr`, excluding `depth`."""
        raise NotImplementedError

    def _key(self) -> tuple[object, ...]:
        return (*self._fields(), self._depth)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Entry) and type(self) is type(other):
            return self._key() == other._key()
        return NotImplemented

    def __hash__(self) -> int:
        return hash((type(self), self._key()))

    def __repr__(self) -> str:
        inner = ", ".join(repr(field) for field in self._fields())
        return f"{type(self).__name__}({inner}{_depth_suffix(self._depth)})"


class File(Entry):
    """A leaf entry: a file named by its `name` filter."""

    __slots__ = ()

    def _fields(self) -> tuple[object, ...]:
        return (self._name,)


class Directory(Entry):
    """An internal entry: a directory named by `name`, holding `children`.

    `children` is materialized to a tuple at construction and preserves
    insertion order. When `name` matches many sibling directories,
    `children` describes the shape shared by every one of them.
    """

    __slots__ = ("_children",)

    def __init__(
        self,
        name: str | list[str] | Filter,
        children: Iterable[Entry] = (),
        *,
        depth: int | None = 1,
    ) -> None:
        super().__init__(name, depth=depth)
        self._children = tuple(children)

    @property
    def children(self) -> tuple[Entry, ...]:
        """The contained entries, in insertion order."""
        return self._children

    def _fields(self) -> tuple[object, ...]:
        return (self._name, self._children)

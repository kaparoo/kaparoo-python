from __future__ import annotations

__all__ = (
    "Directory",
    "Entry",
    "File",
)

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from kaparoo.filesystem.hierarchy.base import Node
from kaparoo.filters import Filter, Literal, OneOf

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


def _depth_suffix(depth: tuple[int, int | None]) -> str:
    """Render the `depth=` part of a `repr` in its most compact form.

    Omitted for the `(1, 1)` default; an exact `(n, n)` renders as
    `depth=n`, `(1, None)` as `depth=None`, and any other range as
    `depth=(min, max)`.
    """
    min_depth, max_depth = depth
    if min_depth == 1 and max_depth == 1:
        return ""
    if min_depth == max_depth:
        return f", depth={min_depth!r}"
    if min_depth == 1 and max_depth is None:
        return ", depth=None"
    return f", depth=({min_depth!r}, {max_depth!r})"


def _normalize_depth(
    depth: int | tuple[int, int | None] | None,
) -> tuple[int, int | None]:
    """Normalize the `depth` argument to an inclusive `(min, max)` range.

    `None` becomes `(1, None)` (any depth), an `int` becomes `(int, int)`
    (an exact level), and a `(min, max)` tuple is taken as-is.

    Raises:
        ValueError: If a bound is less than 1, or `max` is below `min`.
    """
    if depth is None:
        return (1, None)
    if isinstance(depth, tuple):
        min_depth, max_depth = depth
    else:
        min_depth = max_depth = depth
    if min_depth < 1:
        msg = f"depth must be >= 1, got {min_depth!r}"
        raise ValueError(msg)
    if max_depth is not None and max_depth < min_depth:
        msg = f"depth max {max_depth!r} is below min {min_depth!r}"
        raise ValueError(msg)
    return (min_depth, max_depth)


class Entry(Node, ABC):
    """A named node in a filesystem hierarchy: a `File` or a `Directory`.

    Every entry carries a `name` filter. As constructor sugar, a bare
    `str` becomes a `Literal` and a `list[str]` becomes a `OneOf` -- the
    latter lets one node stand for several literally-named siblings that
    share a structure (`Directory(["train", "val"], layout)`). Entries are
    immutable value objects -- equal by type, name, depth, and (for a
    directory) its children -- hashable, with a `repr` that round-trips
    their fields.

    A node's `name` is any `kaparoo.filters.Filter`, so the full filter
    DSL (`Glob`, `Regex`, `And` / `Or` / `Not`, ...) describes which
    siblings a node matches. Names that are also `Expandable` (`Literal`,
    `OneOf`, `Template`) can additionally be enumerated -- the basis for
    scaffolding.

    `depth` is how far below its parent the entry sits, as an inclusive
    `(min_depth, max_depth)` range past intermediate directories of
    unknown name. The default `1` is a direct child. Because the
    intermediate names are unknown, any entry whose depth allows more than
    one level describes structure for *matching*, not scaffolding. This is
    representation only -- the matching that consumes the depth range is
    not implemented yet.

    Args:
        name: The entry's name (a filter, or `str` / `list[str]` sugar).
        depth: How far below the parent the entry sits, exposed as
            `min_depth` / `max_depth`. An `int >= 1` is an exact level,
            `None` is any depth (one or more levels), and a
            `(min, max)` tuple is an inclusive range whose `max` may be
            `None` for unbounded. Defaults to `1` (a direct child).

    Raises:
        ValueError: If a depth bound is below 1, or `max` is below `min`.
    """

    __slots__ = ("_depth", "_name")

    def __init__(
        self,
        name: str | list[str] | Filter,
        *,
        depth: int | tuple[int, int | None] | None = 1,
    ) -> None:
        self._name = _as_filter(name)
        self._depth = _normalize_depth(depth)

    @property
    def name(self) -> Filter:
        """The filter naming this entry (one or many siblings)."""
        return self._name

    @property
    def min_depth(self) -> int:
        """The shallowest level below the parent the entry may sit at."""
        return self._depth[0]

    @property
    def max_depth(self) -> int | None:
        """The deepest level below the parent (`None` is unbounded)."""
        return self._depth[1]

    @abstractmethod
    def _fields(self) -> tuple[object, ...]:
        """Return the identity fields shown in `repr`, excluding `depth`."""
        raise NotImplementedError

    def _key(self) -> tuple[object, ...]:
        return (*self._fields(), self._depth)

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
    insertion order. Each child is any `Node` -- a nested `File` /
    `Directory`, or a `Group` constraint over some of them. When `name`
    matches many sibling directories, `children` describes the shape
    shared by every one of them.
    """

    __slots__ = ("_children",)

    def __init__(
        self,
        name: str | list[str] | Filter,
        children: Iterable[Node] = (),
        *,
        depth: int | tuple[int, int | None] | None = 1,
    ) -> None:
        super().__init__(name, depth=depth)
        self._children = tuple(children)

    @property
    def children(self) -> tuple[Node, ...]:
        """The contained nodes, in insertion order."""
        return self._children

    def _fields(self) -> tuple[object, ...]:
        return (self._name, self._children)

from __future__ import annotations

__all__ = (
    "Exclusive",
    "Group",
    "Together",
)

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, cast

from kaparoo.filesystem.hierarchy.base import Node

if TYPE_CHECKING:
    from collections.abc import Iterable

    from kaparoo.filesystem.hierarchy.entry import Entry


def _normalize_alternative(alternative: Node | Iterable[Node]) -> tuple[Node, ...]:
    """Coerce one `Exclusive` alternative to a tuple of nodes."""
    if isinstance(alternative, Node):
        return (alternative,)
    return tuple(alternative)


class Group(Node, ABC):
    """A constraint over a group of sibling nodes.

    The shared base of `Exclusive` (mutual exclusion) and `Together`
    (co-occurrence). A group is a `Node` but not an `Entry` -- it has no
    name of its own, only the nodes it constrains (which may themselves be
    groups). Every group carries a keyword-only `required` flag (whether
    the empty, none-present case is forbidden; its precise meaning is
    defined by each subclass) and exposes the leaf entries it references
    through `entries`, regardless of how they are structured internally.
    Groups are constraints for *matching* / *validation*, which is not
    implemented yet -- this is representation only.
    """

    __slots__ = ("_required",)

    def __init__(self, *, required: bool = False) -> None:
        self._required = required

    @property
    def required(self) -> bool:
        """Whether the empty (none-present) case is forbidden.

        The exact meaning is subclass-specific: for `Exclusive`, at least
        one alternative must be present; for `Together`, every member.
        """
        return self._required

    @property
    @abstractmethod
    def entries(self) -> tuple[Entry, ...]:
        """The leaf entries this constraint references.

        Flattened in order, descending recursively through any nested
        groups so the result is always concrete `Entry` nodes.
        """
        raise NotImplementedError


def _flatten_entries(nodes: Iterable[Node]) -> tuple[Entry, ...]:
    """Recursively gather the leaf `Entry` nodes from `nodes`."""
    result: list[Entry] = []
    for node in nodes:
        if isinstance(node, Group):
            result.extend(node.entries)
        else:
            result.append(cast("Entry", node))
    return tuple(result)


class Exclusive(Group):
    """A mutual-exclusion constraint among sibling alternatives.

    Placed in a `Directory`'s `children`, `Exclusive` declares that the
    present siblings may come from at most one of its `alternatives`. Each
    alternative is a set of one or more entries on the same side of the
    exclusion -- `Exclusive(File("setup.py"), File("pyproject.toml"))`
    forbids both files coexisting, while `Exclusive([File("setup.py"),
    File("setup.cfg")], File("pyproject.toml"))` lets `setup.py` and
    `setup.cfg` appear together (same side) but not alongside
    `pyproject.toml`.

    Nodes within an alternative are independent -- they need not all be
    present; use `Together` for co-occurrence. An alternative may itself
    contain a `Group` (e.g. a `Together`), so constraints nest:
    `Exclusive(Together(a, b), c)` is "{a and b together} or c". With
    `required=False` (the default) no alternative present is also allowed;
    `required=True` additionally requires at least one alternative to be
    present.

    `Exclusive` is a `Group` (a `Node`, not an `Entry`): it has no name of
    its own, only the nodes grouped in its alternatives; `entries` gives
    the leaf entries it references, descending through any nesting. It is a
    constraint for *matching* / *validation*, which is not implemented yet
    -- this is representation only.

    Args:
        *alternatives: Two or more alternatives, each a `Node` or an
            iterable of nodes sharing one side of the exclusion.
        required: If True, at least one alternative must be present; if
            False (the default), at most one.

    Raises:
        ValueError: If fewer than two alternatives are given, or any
            alternative is empty.
    """

    __slots__ = ("_alternatives",)

    def __init__(
        self,
        *alternatives: Node | Iterable[Node],
        required: bool = False,
    ) -> None:
        normalized = tuple(_normalize_alternative(alt) for alt in alternatives)
        if len(normalized) < 2:
            msg = "Exclusive requires at least two alternatives."
            raise ValueError(msg)
        if any(not alt for alt in normalized):
            msg = "each Exclusive alternative must be non-empty."
            raise ValueError(msg)
        self._alternatives = normalized
        super().__init__(required=required)

    @property
    def alternatives(self) -> tuple[tuple[Node, ...], ...]:
        """The mutually exclusive alternatives, each a tuple of nodes."""
        return self._alternatives

    @property
    def entries(self) -> tuple[Entry, ...]:
        return _flatten_entries(node for alt in self._alternatives for node in alt)

    def _key(self) -> tuple[object, ...]:
        return (self._alternatives, self._required)

    def __repr__(self) -> str:
        parts = [
            repr(alt[0]) if len(alt) == 1 else repr(alt) for alt in self._alternatives
        ]
        if self._required:
            parts.append("required=True")
        return f"Exclusive({', '.join(parts)})"


class Together(Group):
    """A co-occurrence constraint: sibling entries that exist as a unit.

    Placed in a `Directory`'s `children`, `Together` declares its
    `members` all-or-nothing -- either every one exists on disk or none
    does. Use it for entries that are meaningless apart, such as a sharded
    file and its index, or a certificate and its key. It is the dual of
    `Exclusive`, and the two compose by sitting side by side in
    `children`.

    With `required=False` (the default) all-absent is allowed;
    `required=True` additionally requires every member present.

    Members may themselves be groups, so constraints nest; `entries` gives
    the leaf entries, descending through any nesting. Like `Exclusive`,
    `Together` is a `Group` (a `Node`, not an `Entry`) -- it has no name of
    its own, only the nodes it groups. It is a constraint for *matching* /
    *validation*, which is not implemented yet -- this is representation
    only.

    Args:
        *members: Two or more nodes that must coexist.
        required: If True, every member must be present; if False (the
            default), all or none.

    Raises:
        ValueError: If fewer than two members are given.
    """

    __slots__ = ("_members",)

    def __init__(self, *members: Node, required: bool = False) -> None:
        if len(members) < 2:
            msg = "Together requires at least two members."
            raise ValueError(msg)
        self._members = members
        super().__init__(required=required)

    @property
    def members(self) -> tuple[Node, ...]:
        """The nodes that must coexist (all present, or all absent)."""
        return self._members

    @property
    def entries(self) -> tuple[Entry, ...]:
        return _flatten_entries(self._members)

    def _key(self) -> tuple[object, ...]:
        return (self._members, self._required)

    def __repr__(self) -> str:
        parts = [repr(member) for member in self._members]
        if self._required:
            parts.append("required=True")
        return f"Together({', '.join(parts)})"

from __future__ import annotations

__all__ = ("Exclusive", "Group", "Together")

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, cast

from kaparoo.filesystem.hierarchy.base import Node
from kaparoo.filesystem.hierarchy.utils import register_node

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from typing import Any, Literal, Self

    from kaparoo.filesystem.hierarchy.entry import Entry


def _normalize_alternative(alternative: Node | Iterable[Node]) -> tuple[Node, ...]:
    """Coerce one `Exclusive` alternative to a tuple of nodes."""
    if isinstance(alternative, Node):
        return (alternative,)
    return tuple(alternative)


class Group(Node, ABC):
    """A constraint over a group of sibling nodes.

    The shared base of `Exclusive` (mutual exclusion) and `Together`
    (co-occurrence) -- its only two subclasses, which `validate` relies on
    to narrow a non-`Exclusive` `Group` to a `Together`. A group is a `Node`
    but not an `Entry`: it has no name
    of its own, only the nodes it constrains (which may themselves be
    groups). The keyword-only `required` flag forbids the none-present case
    (its precise meaning is subclass-defined); `entries` exposes the leaf
    entries it references, however they are nested.
    """

    __slots__ = ("_required",)

    _required: bool

    def __init__(self, *, required: bool = False) -> None:
        object.__setattr__(self, "_required", required)

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


def flatten_entries(nodes: Iterable[Node]) -> tuple[Entry, ...]:
    """Recursively gather the leaf `Entry` nodes from `nodes`."""
    result: list[Entry] = []
    for node in nodes:
        if isinstance(node, Group):
            result.extend(node.entries)
        else:
            # `Node` is the closed `Entry | Group`, so a non-`Group` is an
            # `Entry` (see `Node`); `ty` cannot prove it from the open ABC.
            result.append(cast("Entry", node))
    return tuple(result)


def max_depth_of(nodes: Iterable[Node]) -> int | None:
    """The deepest level any of `nodes` needs once flattened to entries.

    `None` if any entry's depth is unbounded. Accepts raw nodes (groups
    included), flattening them, so callers need not pre-flatten.
    """
    bound = 1
    for entry in flatten_entries(nodes):
        if entry.max_depth is None:
            return None
        bound = max(bound, entry.max_depth)

    return bound


@register_node("exclusive")
class Exclusive(Group):
    """A mutual-exclusion constraint among sibling alternatives.

    In a `Directory`'s `children`, `Exclusive` declares that present
    siblings may come from at most one of its `alternatives`. Each
    alternative is one or more entries on the same side; nodes within a
    side are independent (use `Together` for co-occurrence). An alternative
    may itself be a `Group`, so constraints nest -- `Exclusive(Together(a,
    b), c)` is "{a and b} or c". `required=True` additionally requires at
    least one alternative present.

    When more than one alternative is present, `on_conflict` decides the
    outcome: `"error"` (the default) reports an `exclusive` violation, while
    `"priority"` resolves the conflict by *declaration order* -- the first
    present alternative wins and the lower-priority present ones are treated
    as `unexpected` (their files no longer belong to the resolved tree).
    Reorder the alternatives to set the priority.

    Args:
        *alternatives: Two or more alternatives, each a `Node` or an
            iterable of nodes sharing one side of the exclusion. Their order
            is the priority used by `on_conflict="priority"`.
        required: If True, at least one alternative must be present; if
            False (the default), at most one.
        on_conflict: How a multi-side conflict is resolved -- `"error"` (the
            default) flags it; `"priority"` keeps the first present side and
            demotes the rest to `unexpected`.

    Raises:
        ValueError: If fewer than two alternatives are given, any
            alternative is empty, or `on_conflict` is not `"error"` /
            `"priority"`.
    """

    __slots__ = ("_alternatives", "_on_conflict")

    _alternatives: tuple[tuple[Node, ...], ...]
    _on_conflict: Literal["error", "priority"]

    def __init__(
        self,
        *alternatives: Node | Iterable[Node],
        required: bool = False,
        on_conflict: Literal["error", "priority"] = "error",
    ) -> None:
        normalized = tuple(_normalize_alternative(alt) for alt in alternatives)
        if len(normalized) < 2:
            msg = "Exclusive requires at least two alternatives."
            raise ValueError(msg)
        if any(not alt for alt in normalized):
            msg = "each Exclusive alternative must be non-empty."
            raise ValueError(msg)
        if on_conflict not in ("error", "priority"):
            msg = (
                "Exclusive on_conflict must be 'error' or 'priority', "
                f"got {on_conflict!r}"
            )
            raise ValueError(msg)
        object.__setattr__(self, "_alternatives", normalized)
        object.__setattr__(self, "_on_conflict", on_conflict)
        super().__init__(required=required)

    @property
    def alternatives(self) -> tuple[tuple[Node, ...], ...]:
        """The mutually exclusive alternatives, each a tuple of nodes."""
        return self._alternatives

    @property
    def on_conflict(self) -> Literal["error", "priority"]:
        """How a multi-side conflict resolves (`"error"` flags, `"priority"` picks)."""
        return self._on_conflict

    @property
    def entries(self) -> tuple[Entry, ...]:
        """The leaf entries across every alternative, flattened in order."""
        return flatten_entries(node for alt in self._alternatives for node in alt)

    def _key(self) -> tuple[object, ...]:
        return (self._alternatives, self._required, self._on_conflict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "node": "exclusive",
            "alternatives": [
                [node.to_dict() for node in alt] for alt in self._alternatives
            ],
        }
        if self._required:
            result["required"] = True
        if self._on_conflict != "error":
            result["on_conflict"] = self._on_conflict
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        alternatives = [
            [Node.from_dict(node) for node in alt] for alt in data["alternatives"]
        ]
        return cls(
            *alternatives,
            required=data.get("required", False),
            on_conflict=data.get("on_conflict", "error"),
        )

    def __repr__(self) -> str:
        parts = [
            repr(alt[0]) if len(alt) == 1 else repr(alt) for alt in self._alternatives
        ]
        if self._required:
            parts.append("required=True")
        if self._on_conflict != "error":
            parts.append(f"on_conflict={self._on_conflict!r}")
        return f"Exclusive({', '.join(parts)})"


@register_node("together")
class Together(Group):
    """A co-occurrence constraint: sibling entries that exist as a unit.

    In a `Directory`'s `children`, `Together` declares its `members`
    all-or-nothing -- every one exists on disk, or none does (a sharded
    file and its index, a certificate and its key). It is the dual of
    `Exclusive`. Members may themselves be groups, so constraints nest.
    `required=True` additionally requires every member present.

    Args:
        *members: Two or more nodes that must coexist.
        required: If True, every member must be present; if False (the
            default), all or none.

    Raises:
        ValueError: If fewer than two members are given.
    """

    __slots__ = ("_members",)

    _members: tuple[Node, ...]

    def __init__(self, *members: Node, required: bool = False) -> None:
        if len(members) < 2:
            msg = "Together requires at least two members."
            raise ValueError(msg)
        object.__setattr__(self, "_members", members)
        super().__init__(required=required)

    @property
    def members(self) -> tuple[Node, ...]:
        """The nodes that must coexist (all present, or all absent)."""
        return self._members

    @property
    def entries(self) -> tuple[Entry, ...]:
        """The leaf entries across every member, flattened in order."""
        return flatten_entries(self._members)

    def _key(self) -> tuple[object, ...]:
        return (self._members, self._required)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "node": "together",
            "members": [member.to_dict() for member in self._members],
        }
        if self._required:
            result["required"] = True
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        members = [Node.from_dict(member) for member in data["members"]]
        return cls(*members, required=data.get("required", False))

    def __repr__(self) -> str:
        parts = [repr(member) for member in self._members]
        if self._required:
            parts.append("required=True")
        return f"Together({', '.join(parts)})"

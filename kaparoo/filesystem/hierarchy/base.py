from __future__ import annotations

__all__ = ("Node",)

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from kaparoo.filesystem.hierarchy.utils import _NODE_REGISTRY

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


class Node(ABC):
    """A member of a hierarchy -- anything that can sit in a directory.

    The shared base of `Entry` (named filesystem nodes) and `Group`
    (unnamed constraint nodes). Nodes are immutable value objects: equal
    when they are the same concrete type with equal `_key`s, and hashable
    on the same basis.

    Nodes serialize to a `"node"`-discriminated dict via `to_dict`,
    round-trippable through `Node.from_dict`. The name and child nodes a
    node holds are serialized recursively (names via the filter's
    `to_dict` / `Filter.from_dict`).
    """

    __slots__ = ()

    @abstractmethod
    def _key(self) -> tuple[object, ...]:
        """Return the fields that define this node's identity."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize to a `"node"`-discriminated dict.

        Round-trippable via `Node.from_dict`. Default-valued fields (a
        `(1, 1)` depth, `required=False`) are omitted for compactness.
        """
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Node:
        """Construct a `Node` from a dict produced by `to_dict`.

        When called on the base (`Node.from_dict(data)`), dispatches by
        `data["node"]` to the registered target class. Concrete subclasses
        override this to construct themselves from `data`'s fields.

        Raises:
            ValueError: If `data` lacks `"node"`, or the kind is not
                registered.
            NotImplementedError: If called on a subclass that did not
                override `from_dict`.
        """
        if cls is not Node:
            msg = f"{cls.__name__}.from_dict() must be overridden by subclasses."
            raise NotImplementedError(msg)

        if (node := data.get("node")) is None:
            msg = "node dict missing 'node' discriminator."
            raise ValueError(msg)

        if (target := _NODE_REGISTRY.get(node)) is None:
            msg = f"unknown node kind: {node!r}"
            raise ValueError(msg)

        return target.from_dict(data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Node) and type(self) is type(other):
            return self._key() == other._key()
        return NotImplemented

    def __hash__(self) -> int:
        return hash((type(self), self._key()))

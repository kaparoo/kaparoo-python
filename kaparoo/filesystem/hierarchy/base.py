from __future__ import annotations

__all__ = ("Node",)

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

from kaparoo.filesystem.hierarchy.utils import _NODE_REGISTRY

if TYPE_CHECKING:
    from typing import Any


class Node(ABC):
    """A member of a hierarchy -- anything that can sit in a directory.

    The shared base of `Entry` (named filesystem nodes) and `Group`
    (unnamed constraint nodes). These are the **only** two direct subtrees:
    `match` / `validate` rely on this closed world to narrow a `Node` that
    is not a `Group` to an `Entry` (via `cast`). A third subtree would make
    those casts unsound, so keep new node kinds under `Entry` or `Group`.
    Nodes are immutable value objects: equal when they are the same concrete
    type with equal `_key`s, and hashable on the same basis.

    Nodes round-trip through `to_dict` / `Node.from_dict` (a
    `"node"`-discriminated registry), recursing into the name filter and
    child nodes.
    """

    __slots__ = ()

    @abstractmethod
    def _key(self) -> tuple[object, ...]:
        """Return the fields that define this node's identity."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize to a `"node"`-discriminated dict.

        Round-trippable via `Node.from_dict`. Subclasses may omit
        default-valued fields for compactness.
        """
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Node:
        """Construct a `Node` from a dict produced by `to_dict`.

        When called on the base (`Node.from_dict(data)`), dispatches by
        `data["node"]` to the registered target class. Concrete subclasses
        override this to construct themselves from `data`'s fields.

        Raises:
            TypeError: If `data` is not a mapping.
            ValueError: If `data` lacks `"node"`, or the kind is not
                registered.
            NotImplementedError: If called on a subclass that did not
                override `from_dict`.
        """
        if cls is not Node:
            msg = f"{cls.__name__}.from_dict() must be overridden by subclasses."
            raise NotImplementedError(msg)

        if not isinstance(data, Mapping):
            msg = f"expected a node dict, got {type(data).__name__}"
            raise TypeError(msg)

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

    def __setattr__(self, name: str, value: object) -> None:
        # Nodes are immutable value objects; subclass `__init__`s assign their
        # fields through `object.__setattr__`. Block assignment afterwards,
        # mirroring the frozen dataclasses used elsewhere in the library.
        msg = f"cannot assign to field {name!r}"
        raise FrozenInstanceError(msg)

    def __delattr__(self, name: str) -> None:
        msg = f"cannot delete field {name!r}"
        raise FrozenInstanceError(msg)

from __future__ import annotations

__all__ = ("register_node",)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from kaparoo.filesystem.hierarchy.base import Node


_NODE_REGISTRY: dict[str, type[Node]] = {}
"""Maps a `"node"` discriminator to a `Node` subclass.

Populated by `register_node` and consulted by `Node.from_dict` for
polymorphic deserialization; mutate only through `register_node`.
"""


def register_node[N: Node](node: str) -> Callable[[type[N]], type[N]]:
    """Register a `Node` subclass under the discriminator `node` (decorator).

    Makes the class discoverable by `Node.from_dict` when it sees
    `{"node": node, ...}`.

    Raises:
        ValueError: If `node` is already registered to another class.
    """

    def decorator(cls: type[N]) -> type[N]:
        existing = _NODE_REGISTRY.get(node)
        if existing is not None and existing is not cls:
            msg = (
                f"node kind {node!r} already registered to "
                f"{existing.__name__}; cannot reassign to {cls.__name__}."
            )
            raise ValueError(msg)

        _NODE_REGISTRY[node] = cls
        return cls

    return decorator

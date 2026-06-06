from __future__ import annotations

__all__ = ()

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from kaparoo.filesystem.hierarchy.base import Node


_NODE_REGISTRY: dict[str, type[Node]] = {}
"""Maps a `"node"` discriminator string to a `Node` subclass.

Populated by the `register_node` decorator at class-definition time and
consulted by `Node.from_dict` for polymorphic deserialization. Treated as
private -- mutate only through `register_node`.
"""


def register_node[N: Node](node: str) -> Callable[[type[N]], type[N]]:
    """Register a `Node` subclass under `node` (decorator).

    The registered class becomes discoverable by `Node.from_dict` when it
    encounters `{"node": node, ...}` in serialized input.

    Args:
        node: The discriminator string written by `to_dict` and read by
            `from_dict` (e.g. `"file"`, `"directory"`, `"exclusive"`).

    Returns:
        A decorator that registers and returns the given class.

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

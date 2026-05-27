from __future__ import annotations

__all__ = ("register_filter",)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from kaparoo.filesystem.search.filters.base import Filter


_FILTER_REGISTRY: dict[str, type[Filter]] = {}
"""Maps a discriminator string to a `Filter` subclass.

Populated by the `register_filter` decorator at class-definition time
and consulted by `Filter.from_dict` for polymorphic deserialization.
Treated as private -- mutate only through `register_filter`.
"""


def register_filter[F: Filter](kind: str) -> Callable[[type[F]], type[F]]:
    """Register a `Filter` subclass under `kind` (decorator).

    The registered class becomes discoverable by `Filter.from_dict`
    when it encounters `{"kind": kind, ...}` in serialized input.

    Args:
        kind: The discriminator string written by `to_dict` and read by
            `from_dict`. Conventionally snake_case (e.g. `"equals"`,
            `"starts_with_any"`).

    Returns:
        A decorator that registers and returns the given class.

    Raises:
        ValueError: If `kind` is already registered to another class.
    """

    def decorator(cls: type[F]) -> type[F]:
        existing = _FILTER_REGISTRY.get(kind)
        if existing is not None and existing is not cls:
            msg = (
                f"filter kind {kind!r} already registered to "
                f"{existing.__name__}; cannot reassign to {cls.__name__}."
            )
            raise ValueError(msg)
        _FILTER_REGISTRY[kind] = cls
        return cls

    return decorator

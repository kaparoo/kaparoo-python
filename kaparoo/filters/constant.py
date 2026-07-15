"""Constant filters whose result ignores the target: `Any`."""

from __future__ import annotations

__all__ = ("Any", "AnyFilter")

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from kaparoo.filters.base import Filter
from kaparoo.filters.utils import register_filter

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Self


@register_filter("any")
@dataclass(frozen=True, repr=False)
class AnyFilter(Filter):
    """A filter matching every string, regardless of content.

    The top element of the filter lattice: `matches` is always `True`, so
    `And(f, Any())` reduces to `f` and `Or(f, Any())` to `Any()`. Prefer it
    to `Glob("*")` as an explicit "match anything" placeholder -- the intent
    reads directly and there is no regex to compile or run. It carries no
    fields (all instances are equal), and it is deliberately not
    `Expandable`: the matching set is infinite, so it cannot be enumerated.
    """

    @override
    def matches(self, target: str) -> bool:
        # Always true -- the target is intentionally ignored.
        return True

    @override
    def _payload(self) -> dict[str, object]:
        return {}

    @classmethod
    @override
    def from_dict(cls, data: Mapping[str, object]) -> Self:
        return cls()

    def __repr__(self) -> str:
        return f"{self._repr_name()}()"


# Short alias. Prefer this in inline composition; prefer the canonical
# `AnyFilter` in type annotations and `isinstance` checks. Like `Literal`
# (vs `typing.Literal`), it shadows `typing.Any` when star-imported.
Any = AnyFilter

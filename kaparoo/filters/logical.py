from __future__ import annotations

__all__ = (
    "And",
    "AndFilter",
    "LogicalFilter",
    "Not",
    "NotFilter",
    "Or",
    "OrFilter",
)

from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kaparoo.filters.base import Filter
from kaparoo.filters.utils import register_filter

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any, Self


@dataclass(frozen=True)
class LogicalFilter(Filter, ABC):
    """Abstract base for composite filters built from other filters.

    Concrete subclasses define their own field shape:
        - `AndFilter` and `OrFilter` take `children: tuple[Filter, ...]`
          and combine multiple results.
        - `NotFilter` takes a single `child: Filter` and inverts it.

    Because children are typed as `Filter`, logical filters can nest
    arbitrarily -- e.g. `AndFilter((f1, NotFilter(OrFilter((f2, f3)))))`.
    Serialization recurses via each child's `to_dict` / `from_dict`.
    """


@register_filter("and")
@dataclass(frozen=True)
class AndFilter(LogicalFilter):
    """Match strings that satisfy ALL of `children` (logical conjunction).

    Attributes:
        children: The component filters. Always non-empty (validated at
            construction).

    Raises:
        ValueError: If `children` is empty.
    """

    children: tuple[Filter, ...]

    def __post_init__(self) -> None:
        if not self.children:
            msg = f"{type(self).__name__} requires at least one child filter."
            raise ValueError(msg)

    def matches(self, target: str) -> bool:
        return all(child.matches(target) for child in self.children)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "and",
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            children=tuple(Filter.from_dict(child) for child in data["children"]),
        )


@register_filter("or")
@dataclass(frozen=True)
class OrFilter(LogicalFilter):
    """Match strings that satisfy AT LEAST ONE of `children` (logical disjunction).

    Attributes:
        children: The component filters. Always non-empty (validated at
            construction).

    Raises:
        ValueError: If `children` is empty.
    """

    children: tuple[Filter, ...]

    def __post_init__(self) -> None:
        if not self.children:
            msg = f"{type(self).__name__} requires at least one child filter."
            raise ValueError(msg)

    def matches(self, target: str) -> bool:
        return any(child.matches(target) for child in self.children)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "or",
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            children=tuple(Filter.from_dict(child) for child in data["children"]),
        )


@register_filter("not")
@dataclass(frozen=True)
class NotFilter(LogicalFilter):
    """Match strings that do NOT satisfy `child` (logical negation).

    Attributes:
        child: The single component filter whose result is inverted.
    """

    child: Filter

    def matches(self, target: str) -> bool:
        return not self.child.matches(target)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "not", "child": self.child.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(child=Filter.from_dict(data["child"]))


# Short aliases. Prefer these in inline composition; prefer the
# canonical `*Filter` names in type annotations and `isinstance` checks.
And = AndFilter
Or = OrFilter
Not = NotFilter

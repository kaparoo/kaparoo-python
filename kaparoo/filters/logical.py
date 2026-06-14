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


@dataclass(frozen=True, repr=False)
class LogicalFilter(Filter, ABC):
    """Abstract base for composite filters built from other filters.

    Concrete subclasses define their own field shape:
        - `AndFilter` and `OrFilter` take `children: tuple[Filter, ...]`
          and combine multiple results (under `NaryLogicalFilter`).
        - `NotFilter` takes a single `child: Filter` and inverts it.

    Because children are typed as `Filter`, logical filters can nest
    arbitrarily -- e.g. `AndFilter((f1, NotFilter(OrFilter((f2, f3)))))`.
    Serialization recurses via each child's `to_dict` / `from_dict`.
    """


@dataclass(frozen=True, repr=False)
class NaryLogicalFilter(LogicalFilter, ABC):
    """Base for logical filters over a non-empty tuple of `children`.

    Subclasses (`AndFilter`, `OrFilter`) supply only the `matches`
    quantifier; field, validation, and serialization are shared.

    Raises:
        ValueError: If `children` is empty.
    """

    children: tuple[Filter, ...]

    def __post_init__(self) -> None:
        if not self.children:
            msg = f"{type(self).__name__} requires at least one child filter."
            raise ValueError(msg)

    def _payload(self) -> dict[str, Any]:
        return {"children": [child.to_dict() for child in self.children]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            children=tuple(Filter.from_dict(child) for child in data["children"]),
        )

    def __repr__(self) -> str:
        children = ", ".join(repr(child) for child in self.children)
        return f"{type(self).__name__}({children})"


@register_filter("and")
@dataclass(frozen=True, repr=False)
class AndFilter(NaryLogicalFilter):
    """A filter matching strings that satisfy ALL of `children` (logical conjunction)."""

    def matches(self, target: str) -> bool:
        return all(child.matches(target) for child in self.children)


@register_filter("or")
@dataclass(frozen=True, repr=False)
class OrFilter(NaryLogicalFilter):
    """A filter matching strings that satisfy AT LEAST ONE of `children` (disjunction)."""

    def matches(self, target: str) -> bool:
        return any(child.matches(target) for child in self.children)


@register_filter("not")
@dataclass(frozen=True, repr=False)
class NotFilter(LogicalFilter):
    """A filter matching strings that do NOT satisfy `child` (logical negation)."""

    child: Filter

    def matches(self, target: str) -> bool:
        return not self.child.matches(target)

    def _payload(self) -> dict[str, Any]:
        return {"child": self.child.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(child=Filter.from_dict(data["child"]))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.child!r})"


# Short aliases. Prefer these in inline composition; prefer the
# canonical `*Filter` names in type annotations and `isinstance` checks.
And = AndFilter
Or = OrFilter
Not = NotFilter

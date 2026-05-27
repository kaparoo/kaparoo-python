from __future__ import annotations

__all__ = (
    "ContainsAny",
    "ContainsAnyFilter",
    "EndsWithAny",
    "EndsWithAnyFilter",
    "EqualsAny",
    "EqualsAnyFilter",
    "MultiPatternFilter",
    "StartsWithAny",
    "StartsWithAnyFilter",
)

from abc import ABC
from dataclasses import dataclass, field

from kaparoo.filesystem.search.filters.base import Filter


@dataclass(frozen=True)
class MultiPatternFilter(Filter, ABC):
    """Abstract base for matching rules with multiple patterns (any-of).

    Concrete subclasses (`EqualsAnyFilter`, `StartsWithAnyFilter`,
    `EndsWithAnyFilter`, `ContainsAnyFilter`, or user-defined) implement
    `matches` to return True if the input satisfies ANY of `patterns`.

    Attributes:
        patterns: The strings compared against the input. Must be non-empty.
        case_sensitive: If False, matching is performed case-insensitively
            via Unicode `casefold`. Defaults to True.

    Raises:
        ValueError: If `patterns` is empty.
    """

    patterns: tuple[str, ...]
    case_sensitive: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        if not self.patterns:
            msg = f"{type(self).__name__} requires at least one pattern."
            raise ValueError(msg)
        normalized = (
            self.patterns
            if self.case_sensitive
            else tuple(p.casefold() for p in self.patterns)
        )
        deduped = tuple(dict.fromkeys(normalized))
        if deduped != self.patterns:
            object.__setattr__(self, "patterns", deduped)

    def _prepare_target(self, target: str) -> str:
        """Return `target` normalized for `case_sensitive`."""
        return target if self.case_sensitive else target.casefold()


@dataclass(frozen=True)
class EqualsAnyFilter(MultiPatternFilter):
    """Match strings that equal ANY of `patterns`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target) in self.patterns


@dataclass(frozen=True)
class StartsWithAnyFilter(MultiPatternFilter):
    """Match strings that start with ANY of `patterns`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).startswith(self.patterns)


@dataclass(frozen=True)
class EndsWithAnyFilter(MultiPatternFilter):
    """Match strings that end with ANY of `patterns`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).endswith(self.patterns)


@dataclass(frozen=True)
class ContainsAnyFilter(MultiPatternFilter):
    """Match strings that contain ANY of `patterns` as a substring."""

    def matches(self, target: str) -> bool:
        t = self._prepare_target(target)
        return any(p in t for p in self.patterns)


# Short aliases. Prefer these in inline composition; prefer the
# canonical `*Filter` names in type annotations and `isinstance` checks.
EqualsAny = EqualsAnyFilter
StartsWithAny = StartsWithAnyFilter
EndsWithAny = EndsWithAnyFilter
ContainsAny = ContainsAnyFilter

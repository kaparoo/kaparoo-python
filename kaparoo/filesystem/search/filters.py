from __future__ import annotations

__all__ = (
    "ContainsFilter",
    "EndsWithFilter",
    "EqualsFilter",
    "Filter",
    "StartsWithFilter",
)

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Filter(ABC):
    """Abstract base for matching rules with include/exclude polarity.

    Concrete subclasses (`EqualsFilter`, `StartsWithFilter`,
    `EndsWithFilter`, `ContainsFilter`, or user-defined) implement
    `matches` to compare the input against `pattern`. Polarity
    (`include`) is metadata for the composer (e.g. exclude-wins) and
    is not consulted by `matches` itself.

    Attributes:
        pattern: The string compared against the input.
        include: If True, this is a positive (allow) rule; if False,
            a negative (deny) rule. Defaults to True.
        case_sensitive: If False, matching is performed case-insensitively
            via Unicode `casefold`. Defaults to True.
    """

    pattern: str
    include: bool = True
    case_sensitive: bool = True

    def _prepare(self, s: str) -> tuple[str, str]:
        """Return `(pattern, target)` normalized for `case_sensitive`."""
        if self.case_sensitive:
            return self.pattern, s
        return self.pattern.casefold(), s.casefold()

    @abstractmethod
    def matches(self, s: str) -> bool:
        """Test whether `s` satisfies this filter's pattern.

        The result ignores `include`; the caller applies polarity when
        composing multiple filters.
        """


@dataclass(frozen=True)
class EqualsFilter(Filter):
    """Match strings that equal `pattern` exactly."""

    def matches(self, s: str) -> bool:
        pattern, target = self._prepare(s)
        return target == pattern


@dataclass(frozen=True)
class StartsWithFilter(Filter):
    """Match strings that start with `pattern`."""

    def matches(self, s: str) -> bool:
        pattern, target = self._prepare(s)
        return target.startswith(pattern)


@dataclass(frozen=True)
class EndsWithFilter(Filter):
    """Match strings that end with `pattern`."""

    def matches(self, s: str) -> bool:
        pattern, target = self._prepare(s)
        return target.endswith(pattern)


@dataclass(frozen=True)
class ContainsFilter(Filter):
    """Match strings that contain `pattern` as a substring."""

    def matches(self, s: str) -> bool:
        pattern, target = self._prepare(s)
        return pattern in target

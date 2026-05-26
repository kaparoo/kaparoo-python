from __future__ import annotations

__all__ = (
    "AndFilter",
    "BaseFilter",
    "ContainsFilter",
    "EndsWithFilter",
    "EqualsFilter",
    "Filter",
    "GlobFilter",
    "LogicalFilter",
    "OrFilter",
    "RegexFilter",
    "StartsWithFilter",
)

import fnmatch
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BaseFilter(ABC):
    """Abstract base for any filter (pattern-based or logical composition).

    Two subclass families live under this base:
        - `Filter` and its concretes: leaf rules that compare an input
          string against a single `pattern`.
        - `LogicalFilter` and its concretes: composite rules that combine
          the results of one or more child filters.

    Attributes:
        include: Polarity metadata (allow vs deny). Not consulted by
            `matches` itself -- composers (e.g. `Search`) inspect it to
            decide what to do with a positive match. Defaults to True.
    """

    include: bool = field(default=True, kw_only=True)

    @abstractmethod
    def matches(self, s: str) -> bool:
        """Test whether `s` satisfies this filter."""


@dataclass(frozen=True)
class Filter(BaseFilter, ABC):
    """Abstract base for string-pattern matching rules.

    Concrete subclasses (`EqualsFilter`, `StartsWithFilter`,
    `EndsWithFilter`, `ContainsFilter`, `RegexFilter`, `GlobFilter`, or
    user-defined) implement `matches` to compare the input against
    `pattern`. Polarity (`include`) is inherited from `BaseFilter` and
    is not consulted by `matches`.

    Attributes:
        pattern: The string compared against the input.
        case_sensitive: If False, matching is performed case-insensitively
            via Unicode `casefold`. Defaults to True.
    """

    pattern: str
    case_sensitive: bool = field(default=True, kw_only=True)

    def _prepare(self, s: str) -> tuple[str, str]:
        """Return `(pattern, target)` normalized for `case_sensitive`."""
        if self.case_sensitive:
            return self.pattern, s
        return self.pattern.casefold(), s.casefold()


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


@dataclass(frozen=True)
class RegexFilter(Filter):
    """Match strings against a regular expression (full-string match).

    Uses `re.fullmatch` semantics: the entire string must match the
    pattern. For partial matches, anchor explicitly with `.*` in the
    pattern. `case_sensitive=False` is wired via `re.IGNORECASE`.

    Raises:
        ValueError: If `pattern` is not a valid regular expression
            (validated at construction).
    """

    def __post_init__(self) -> None:
        try:
            re.compile(self.pattern)
        except re.error as e:
            msg = f"invalid regex pattern {self.pattern!r}: {e}"
            raise ValueError(msg) from e

    def matches(self, s: str) -> bool:
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return bool(re.fullmatch(self.pattern, s, flags))


@dataclass(frozen=True)
class GlobFilter(Filter):
    """Match strings against a POSIX glob pattern via `fnmatch`.

    Supported wildcards: `*` (any sequence), `?` (single char),
    `[seq]` (any in seq), `[!seq]` (any not in seq). Recursive `**`
    is not supported (that is a `pathlib.Path.rglob` concept).
    """

    def matches(self, s: str) -> bool:
        pattern, target = self._prepare(s)
        return fnmatch.fnmatchcase(target, pattern)


@dataclass(frozen=True)
class LogicalFilter(BaseFilter, ABC):
    """Abstract base for composite filters built from other filters.

    Concrete subclasses (`AndFilter`, `OrFilter`) implement `matches`
    by combining the results of `children`. Because `children` is
    `tuple[BaseFilter, ...]`, logical filters can nest arbitrarily --
    e.g. `AndFilter((f1, OrFilter((f2, f3))))`.

    Attributes:
        children: The component filters. Always non-empty (validated at
            construction).

    Raises:
        ValueError: If `children` is empty.
    """

    children: tuple[BaseFilter, ...]

    def __post_init__(self) -> None:
        if not self.children:
            msg = f"{type(self).__name__} requires at least one child filter."
            raise ValueError(msg)


@dataclass(frozen=True)
class AndFilter(LogicalFilter):
    """Match strings that satisfy ALL of `children` (logical conjunction)."""

    def matches(self, s: str) -> bool:
        return all(child.matches(s) for child in self.children)


@dataclass(frozen=True)
class OrFilter(LogicalFilter):
    """Match strings that satisfy AT LEAST ONE of `children` (logical disjunction)."""

    def matches(self, s: str) -> bool:
        return any(child.matches(s) for child in self.children)

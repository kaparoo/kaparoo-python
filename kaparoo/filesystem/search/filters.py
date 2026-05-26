from __future__ import annotations

__all__ = (
    "And",
    "AndFilter",
    "Contains",
    "ContainsFilter",
    "EndsWith",
    "EndsWithFilter",
    "Equals",
    "EqualsFilter",
    "Filter",
    "Glob",
    "GlobFilter",
    "LogicalFilter",
    "Not",
    "NotFilter",
    "Or",
    "OrFilter",
    "PatternFilter",
    "Regex",
    "RegexFilter",
    "StartsWith",
    "StartsWithFilter",
)

import fnmatch
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Filter(ABC):
    """Abstract base for any filter (pattern-based or logical composition).

    Two subclass families live under this base:
        - `PatternFilter` and its concretes: leaf rules that compare an
          input string against a single `pattern`.
        - `LogicalFilter` and its concretes: composite rules that combine
          the results of one or more child filters.

    Attributes:
        include: Polarity metadata (allow vs deny). Not consulted by
            `matches` itself -- composers (e.g. `Search`) inspect it to
            decide what to do with a positive match. Defaults to True.
    """

    include: bool = field(default=True, kw_only=True)

    @abstractmethod
    def matches(self, target: str) -> bool:
        """Test whether `target` satisfies this filter."""


@dataclass(frozen=True)
class PatternFilter(Filter, ABC):
    """Abstract base for string-pattern matching rules.

    Concrete subclasses (`EqualsFilter`, `StartsWithFilter`,
    `EndsWithFilter`, `ContainsFilter`, `RegexFilter`, `GlobFilter`, or
    user-defined) implement `matches` to compare the input against
    `pattern`. Polarity (`include`) is inherited from `Filter` and is
    not consulted by `matches`.

    Attributes:
        pattern: The string compared against the input.
        case_sensitive: If False, matching is performed case-insensitively
            via Unicode `casefold`. Defaults to True.
    """

    pattern: str
    case_sensitive: bool = field(default=True, kw_only=True)

    def _prepare(self, target: str) -> tuple[str, str]:
        """Return `(pattern, target)` normalized for `case_sensitive`."""
        if self.case_sensitive:
            return self.pattern, target
        return self.pattern.casefold(), target.casefold()


@dataclass(frozen=True)
class EqualsFilter(PatternFilter):
    """Match strings that equal `pattern` exactly."""

    def matches(self, target: str) -> bool:
        pattern, target = self._prepare(target)
        return target == pattern


@dataclass(frozen=True)
class StartsWithFilter(PatternFilter):
    """Match strings that start with `pattern`."""

    def matches(self, target: str) -> bool:
        pattern, target = self._prepare(target)
        return target.startswith(pattern)


@dataclass(frozen=True)
class EndsWithFilter(PatternFilter):
    """Match strings that end with `pattern`."""

    def matches(self, target: str) -> bool:
        pattern, target = self._prepare(target)
        return target.endswith(pattern)


@dataclass(frozen=True)
class ContainsFilter(PatternFilter):
    """Match strings that contain `pattern` as a substring."""

    def matches(self, target: str) -> bool:
        pattern, target = self._prepare(target)
        return pattern in target


@dataclass(frozen=True)
class RegexFilter(PatternFilter):
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

    def matches(self, target: str) -> bool:
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return bool(re.fullmatch(self.pattern, target, flags))


@dataclass(frozen=True)
class GlobFilter(PatternFilter):
    """Match strings against a POSIX glob pattern via `fnmatch`.

    Supported wildcards: `*` (any sequence), `?` (single char),
    `[seq]` (any in seq), `[!seq]` (any not in seq). Recursive `**`
    is not supported (that is a `pathlib.Path.rglob` concept).
    """

    def matches(self, target: str) -> bool:
        pattern, target = self._prepare(target)
        return fnmatch.fnmatchcase(target, pattern)


@dataclass(frozen=True)
class LogicalFilter(Filter, ABC):
    """Abstract base for composite filters built from other filters.

    Concrete subclasses define their own field shape:
        - `AndFilter` and `OrFilter` take `children: tuple[Filter, ...]`
          and combine multiple results.
        - `NotFilter` takes a single `child: Filter` and inverts it.

    Because children are typed as `Filter`, logical filters can nest
    arbitrarily -- e.g. `AndFilter((f1, NotFilter(OrFilter((f2, f3)))))`.
    Polarity (`include`) is inherited from `Filter`.
    """


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


@dataclass(frozen=True)
class NotFilter(LogicalFilter):
    """Match strings that do NOT satisfy `child` (logical negation).

    Distinct from `include=False`: the latter is composer metadata not
    consulted by `matches`, while `NotFilter` inverts the actual
    `matches` result of its child.

    Attributes:
        child: The single component filter whose result is inverted.
    """

    child: Filter

    def matches(self, target: str) -> bool:
        return not self.child.matches(target)


# Short aliases. Prefer these in inline composition; prefer the
# canonical `*Filter` names in type annotations and `isinstance` checks.
And = AndFilter
Or = OrFilter
Not = NotFilter

Equals = EqualsFilter
StartsWith = StartsWithFilter
EndsWith = EndsWithFilter
Contains = ContainsFilter
Regex = RegexFilter
Glob = GlobFilter

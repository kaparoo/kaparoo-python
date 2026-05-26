from __future__ import annotations

__all__ = (
    "And",
    "AndFilter",
    "Contains",
    "ContainsAny",
    "ContainsAnyFilter",
    "ContainsFilter",
    "EndsWith",
    "EndsWithAny",
    "EndsWithAnyFilter",
    "EndsWithFilter",
    "Equals",
    "EqualsAny",
    "EqualsAnyFilter",
    "EqualsFilter",
    "Filter",
    "Glob",
    "GlobFilter",
    "LogicalFilter",
    "MultiPatternFilter",
    "Not",
    "NotFilter",
    "Or",
    "OrFilter",
    "PatternFilter",
    "Regex",
    "RegexFilter",
    "StartsWith",
    "StartsWithAny",
    "StartsWithAnyFilter",
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

    When `case_sensitive=False`, `pattern` is `casefold`-normalized
    once in `__post_init__` so `matches` only has to normalize the
    (per-call) target. Subclasses with non-`casefold` case-insensitivity
    (e.g. `RegexFilter` via `re.IGNORECASE`) override `__post_init__`
    to skip this step.

    Attributes:
        pattern: The string compared against the input.
        case_sensitive: If False, matching is performed case-insensitively
            via Unicode `casefold`. Defaults to True.
    """

    pattern: str
    case_sensitive: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        if not self.case_sensitive:
            object.__setattr__(self, "pattern", self.pattern.casefold())

    def _prepare_target(self, target: str) -> str:
        """Return `target` normalized for `case_sensitive`."""
        return target if self.case_sensitive else target.casefold()


@dataclass(frozen=True)
class EqualsFilter(PatternFilter):
    """Match strings that equal `pattern` exactly."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target) == self.pattern


@dataclass(frozen=True)
class StartsWithFilter(PatternFilter):
    """Match strings that start with `pattern`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).startswith(self.pattern)


@dataclass(frozen=True)
class EndsWithFilter(PatternFilter):
    """Match strings that end with `pattern`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).endswith(self.pattern)


@dataclass(frozen=True)
class ContainsFilter(PatternFilter):
    """Match strings that contain `pattern` as a substring."""

    def matches(self, target: str) -> bool:
        return self.pattern in self._prepare_target(target)


@dataclass(frozen=True)
class RegexFilter(PatternFilter):
    """Match strings against a regular expression (full-string match).

    Uses `re.fullmatch` semantics: the entire string must match the
    pattern. For partial matches, anchor explicitly with `.*` in the
    pattern. `case_sensitive=False` is wired via `re.IGNORECASE`.

    The pattern is compiled with the appropriate flags once at
    construction and stored in `_compiled`, so `matches` is a single
    `re.Pattern.fullmatch` call -- no per-call flag computation, and
    `re`'s internal pattern cache is bypassed entirely.

    Raises:
        ValueError: If `pattern` is not a valid regular expression
            (validated at construction).
    """

    _compiled: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Intentionally skip `PatternFilter.__post_init__`: regex
        # case-insensitivity uses `re.IGNORECASE`, and casefolding the
        # pattern would corrupt constructs like `(?-i:[A-Z])`.
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            compiled = re.compile(self.pattern, flags)
        except re.error as e:
            msg = f"invalid regex pattern {self.pattern!r}: {e}"
            raise ValueError(msg) from e
        object.__setattr__(self, "_compiled", compiled)

    def matches(self, target: str) -> bool:
        return self._compiled.fullmatch(target) is not None


@dataclass(frozen=True)
class GlobFilter(PatternFilter):
    """Match strings against a POSIX glob pattern via `fnmatch`.

    Supported wildcards: `*` (any sequence), `?` (single char),
    `[seq]` (any in seq), `[!seq]` (any not in seq). Recursive `**`
    is not supported (that is a `pathlib.Path.rglob` concept).
    """

    def matches(self, target: str) -> bool:
        return fnmatch.fnmatchcase(self._prepare_target(target), self.pattern)


@dataclass(frozen=True)
class MultiPatternFilter(Filter, ABC):
    """Abstract base for matching rules with multiple patterns (any-of).

    Concrete subclasses (`EqualsAnyFilter`, `StartsWithAnyFilter`,
    `EndsWithAnyFilter`, `ContainsAnyFilter`, or user-defined) implement
    `matches` to return True if the input satisfies ANY of `patterns`.
    Polarity (`include`) is inherited from `Filter` and is not consulted
    by `matches`.

    In `__post_init__`, `patterns` is `casefold`-normalized when
    `case_sensitive=False` and then deduplicated while preserving
    first-seen order, so `matches` operates on a minimal, ready-to-use
    tuple.

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

EqualsAny = EqualsAnyFilter
StartsWithAny = StartsWithAnyFilter
EndsWithAny = EndsWithAnyFilter
ContainsAny = ContainsAnyFilter

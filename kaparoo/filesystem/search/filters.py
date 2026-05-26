from __future__ import annotations

__all__ = (
    "ContainsFilter",
    "EndsWithFilter",
    "EqualsFilter",
    "Filter",
    "GlobFilter",
    "RegexFilter",
    "StartsWithFilter",
)

import fnmatch
import re
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

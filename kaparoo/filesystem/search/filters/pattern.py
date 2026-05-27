from __future__ import annotations

__all__ = (
    "Contains",
    "ContainsFilter",
    "EndsWith",
    "EndsWithFilter",
    "Equals",
    "EqualsFilter",
    "Glob",
    "GlobFilter",
    "PatternFilter",
    "Regex",
    "RegexFilter",
    "StartsWith",
    "StartsWithFilter",
)

import fnmatch
import re
from abc import ABC
from dataclasses import dataclass, field

from kaparoo.filesystem.search.filters.base import Filter


@dataclass(frozen=True)
class PatternFilter(Filter, ABC):
    """Abstract base for string-pattern matching rules.

    Concrete subclasses (`EqualsFilter`, `StartsWithFilter`,
    `EndsWithFilter`, `ContainsFilter`, `RegexFilter`, `GlobFilter`, or
    user-defined) implement `matches` to compare the input against
    `pattern`.

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


# Short aliases. Prefer these in inline composition; prefer the
# canonical `*Filter` names in type annotations and `isinstance` checks.
Equals = EqualsFilter
StartsWith = StartsWithFilter
EndsWith = EndsWithFilter
Contains = ContainsFilter
Regex = RegexFilter
Glob = GlobFilter

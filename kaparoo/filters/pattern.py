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
from typing import TYPE_CHECKING

from kaparoo.filters.base import Filter
from kaparoo.filters.utils import register_filter

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any, Self


@dataclass(frozen=True)
class PatternFilter(Filter, ABC):
    """Abstract base for string-pattern matching rules.

    Concrete subclasses (`EqualsFilter`, `StartsWithFilter`,
    `EndsWithFilter`, `ContainsFilter`, `RegexFilter`, `GlobFilter`, or
    user-defined) implement `matches` to compare the input against
    `pattern`.

    Attributes:
        pattern: The string compared against the input. When
            `case_sensitive=False`, the stored and serialized form is
            `casefold`-ed.
        case_sensitive: If False, matching uses Unicode `str.casefold()`.
            Defaults to True. See the module README's "Case sensitivity"
            section for the linguistic-equivalence caveat.
    """

    pattern: str
    case_sensitive: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        if not self.case_sensitive:
            object.__setattr__(self, "pattern", self.pattern.casefold())

    def _prepare_target(self, target: str) -> str:
        """Return `target` normalized for `case_sensitive`."""
        return target if self.case_sensitive else target.casefold()

    def _payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"pattern": self.pattern}
        if not self.case_sensitive:
            payload["case_sensitive"] = False
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            pattern=data["pattern"],
            case_sensitive=data.get("case_sensitive", True),
        )


@register_filter("equals")
@dataclass(frozen=True)
class EqualsFilter(PatternFilter):
    """Match strings that equal `pattern` exactly."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target) == self.pattern


@register_filter("starts_with")
@dataclass(frozen=True)
class StartsWithFilter(PatternFilter):
    """Match strings that start with `pattern`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).startswith(self.pattern)


@register_filter("ends_with")
@dataclass(frozen=True)
class EndsWithFilter(PatternFilter):
    """Match strings that end with `pattern`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).endswith(self.pattern)


@register_filter("contains")
@dataclass(frozen=True)
class ContainsFilter(PatternFilter):
    """Match strings that contain `pattern` as a substring."""

    def matches(self, target: str) -> bool:
        return self.pattern in self._prepare_target(target)


@register_filter("regex")
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


@register_filter("glob")
@dataclass(frozen=True)
class GlobFilter(PatternFilter):
    """Match strings against a POSIX glob pattern via `fnmatch`.

    Supported wildcards: `*` (any sequence), `?` (single char),
    `[seq]` (any in seq), `[!seq]` (any not in seq). Recursive `**`
    is not supported (that is a `pathlib.Path.rglob` concept).
    `case_sensitive=False` is wired via `re.IGNORECASE`.
    """

    _compiled: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Intentionally skip `PatternFilter.__post_init__`: like `RegexFilter`,
        # glob case-insensitivity uses `re.IGNORECASE`, not casefolding --
        # casefold is not length-preserving and would desync `?` / `[seq]` on a
        # character whose fold expands (e.g. "ß" -> "ss").
        flags = 0 if self.case_sensitive else re.IGNORECASE
        object.__setattr__(
            self, "_compiled", re.compile(fnmatch.translate(self.pattern), flags)
        )

    def matches(self, target: str) -> bool:
        return self._compiled.match(target) is not None


# Short aliases. Prefer these in inline composition; prefer the
# canonical `*Filter` names in type annotations and `isinstance` checks.
Equals = EqualsFilter
StartsWith = StartsWithFilter
EndsWith = EndsWithFilter
Contains = ContainsFilter
Regex = RegexFilter
Glob = GlobFilter

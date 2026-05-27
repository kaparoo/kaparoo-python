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
from typing import TYPE_CHECKING

from kaparoo.filesystem.search.filters.base import Filter
from kaparoo.filesystem.search.filters.utils import register_filter

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any, Self


@dataclass(frozen=True)
class MultiPatternFilter(Filter, ABC):
    """Abstract base for matching rules with multiple patterns (any-of).

    Concrete subclasses (`EqualsAnyFilter`, `StartsWithAnyFilter`,
    `EndsWithAnyFilter`, `ContainsAnyFilter`, or user-defined) implement
    `matches` to return True if the input satisfies ANY of `patterns`.

    Attributes:
        patterns: The strings compared against the input. Must be non-empty.
            When `case_sensitive=False`, each entry is `casefold`-ed and the
            tuple is deduped at construction time; the normalized form is
            what gets stored and serialized.
        case_sensitive: If False, matching is performed case-insensitively
            via Unicode `str.casefold()`. Note that `casefold()` is more
            aggressive than `str.lower()` (e.g. ``"ß".casefold() == "ss"``,
            ``"ﬁ".casefold() == "fi"``), so two filenames that the
            underlying filesystem treats as distinct may still match each
            other here. This is the "caseless linguistic equivalence"
            interpretation that Python recommends for case-insensitive
            string matching. Defaults to True.

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


def _multi_to_dict(kind: str, f: MultiPatternFilter) -> dict[str, Any]:
    """Build a `MultiPatternFilter` serialization dict; omit default `case_sensitive`."""
    d: dict[str, Any] = {"kind": kind, "patterns": list(f.patterns)}
    if not f.case_sensitive:
        d["case_sensitive"] = False
    return d


def _multi_from_dict[T: MultiPatternFilter](cls: type[T], data: Mapping[str, Any]) -> T:
    """Build a `MultiPatternFilter` subclass from a serialization dict."""
    return cls(
        patterns=tuple(data["patterns"]),
        case_sensitive=data.get("case_sensitive", True),
    )


@register_filter("equals_any")
@dataclass(frozen=True)
class EqualsAnyFilter(MultiPatternFilter):
    """Match strings that equal ANY of `patterns`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target) in self.patterns

    def to_dict(self) -> dict[str, Any]:
        return _multi_to_dict("equals_any", self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return _multi_from_dict(cls, data)


@register_filter("starts_with_any")
@dataclass(frozen=True)
class StartsWithAnyFilter(MultiPatternFilter):
    """Match strings that start with ANY of `patterns`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).startswith(self.patterns)

    def to_dict(self) -> dict[str, Any]:
        return _multi_to_dict("starts_with_any", self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return _multi_from_dict(cls, data)


@register_filter("ends_with_any")
@dataclass(frozen=True)
class EndsWithAnyFilter(MultiPatternFilter):
    """Match strings that end with ANY of `patterns`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).endswith(self.patterns)

    def to_dict(self) -> dict[str, Any]:
        return _multi_to_dict("ends_with_any", self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return _multi_from_dict(cls, data)


@register_filter("contains_any")
@dataclass(frozen=True)
class ContainsAnyFilter(MultiPatternFilter):
    """Match strings that contain ANY of `patterns` as a substring."""

    def matches(self, target: str) -> bool:
        t = self._prepare_target(target)
        return any(p in t for p in self.patterns)

    def to_dict(self) -> dict[str, Any]:
        return _multi_to_dict("contains_any", self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return _multi_from_dict(cls, data)


# Short aliases. Prefer these in inline composition; prefer the
# canonical `*Filter` names in type annotations and `isinstance` checks.
EqualsAny = EqualsAnyFilter
StartsWithAny = StartsWithAnyFilter
EndsWithAny = EndsWithAnyFilter
ContainsAny = ContainsAnyFilter

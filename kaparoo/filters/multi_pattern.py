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

from kaparoo.filters.base import Filter
from kaparoo.filters.utils import register_filter

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any, Self


@dataclass(frozen=True, repr=False)
class MultiPatternFilter(Filter, ABC):
    """Abstract base for matching rules with multiple patterns (any-of).

    Concrete subclasses (`EqualsAnyFilter`, `StartsWithAnyFilter`,
    `EndsWithAnyFilter`, `ContainsAnyFilter`, or user-defined) implement
    `matches` to return True if the input satisfies ANY of `patterns`.

    Attributes:
        patterns: The strings compared against the input. Must be non-empty.
            Deduped at construction; when `case_sensitive=False`, each entry
            is `casefold`-ed first. The normalized form is stored and
            serialized.
        case_sensitive: If False, matching uses Unicode `str.casefold()`.
            Defaults to True. See the module README's "Case sensitivity"
            section for the linguistic-equivalence caveat.

    Raises:
        ValueError: If `patterns` is empty.
    """

    patterns: tuple[str, ...]
    case_sensitive: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        if not self.patterns:
            msg = f"{type(self).__name__} requires at least one pattern."
            raise ValueError(msg)

        patterns = self.patterns
        if not self.case_sensitive:
            patterns = tuple(p.casefold() for p in patterns)

        # Always store a deduped tuple: `startswith` / `endswith` require a
        # tuple (not a list), and dedup keeps first-seen order.
        object.__setattr__(self, "patterns", tuple(dict.fromkeys(patterns)))

    def _prepare_target(self, target: str) -> str:
        """Return `target` normalized for `case_sensitive`."""
        return target if self.case_sensitive else target.casefold()

    def _payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"patterns": list(self.patterns)}
        if not self.case_sensitive:
            payload["case_sensitive"] = False
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            patterns=tuple(data["patterns"]),
            case_sensitive=data.get("case_sensitive", True),
        )

    def __repr__(self) -> str:
        cs = "" if self.case_sensitive else ", case_sensitive=False"
        return f"{type(self).__name__}({self.patterns!r}{cs})"


@register_filter("equals_any")
@dataclass(frozen=True, repr=False)
class EqualsAnyFilter(MultiPatternFilter):
    """A filter matching strings that equal ANY of `patterns`."""

    _pattern_set: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        super().__post_init__()  # validate / casefold / dedupe `patterns`
        object.__setattr__(self, "_pattern_set", frozenset(self.patterns))

    def matches(self, target: str) -> bool:
        return self._prepare_target(target) in self._pattern_set


@register_filter("starts_with_any")
@dataclass(frozen=True, repr=False)
class StartsWithAnyFilter(MultiPatternFilter):
    """A filter matching strings that start with ANY of `patterns`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).startswith(self.patterns)


@register_filter("ends_with_any")
@dataclass(frozen=True, repr=False)
class EndsWithAnyFilter(MultiPatternFilter):
    """A filter matching strings that end with ANY of `patterns`."""

    def matches(self, target: str) -> bool:
        return self._prepare_target(target).endswith(self.patterns)


@register_filter("contains_any")
@dataclass(frozen=True, repr=False)
class ContainsAnyFilter(MultiPatternFilter):
    """A filter matching strings that contain ANY of `patterns` as a substring."""

    def matches(self, target: str) -> bool:
        t = self._prepare_target(target)
        return any(p in t for p in self.patterns)


# Short aliases. Prefer these in inline composition; prefer the
# canonical `*Filter` names in type annotations and `isinstance` checks.
EqualsAny = EqualsAnyFilter
StartsWithAny = StartsWithAnyFilter
EndsWithAny = EndsWithAnyFilter
ContainsAny = ContainsAnyFilter

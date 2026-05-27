from __future__ import annotations

__all__ = (
    "FilterDict",
    "LogicalChildFilterDict",
    "LogicalChildrenFilterDict",
    "MultiPatternFilterDict",
    "PatternFilterDict",
)

from typing import NotRequired, TypedDict


class FilterDict(TypedDict):
    """Base filter dict shape; requires only the `kind` discriminator.

    Family subclasses add their own fields; user-defined filter dicts
    should likewise extend this base to type-check against `Filter.parse`.
    """

    kind: str


class PatternFilterDict(FilterDict):
    """Single-pattern filter dict (`PatternFilter` family)."""

    pattern: str
    case_sensitive: NotRequired[bool]


class MultiPatternFilterDict(FilterDict):
    """Multi-pattern (any-of) filter dict (`MultiPatternFilter` family)."""

    patterns: list[str]
    case_sensitive: NotRequired[bool]


class LogicalChildrenFilterDict(FilterDict):
    """Multi-child logical filter dict (`AndFilter` / `OrFilter`)."""

    children: list[FilterDict]


class LogicalChildFilterDict(FilterDict):
    """Single-child logical filter dict (`NotFilter`)."""

    child: FilterDict

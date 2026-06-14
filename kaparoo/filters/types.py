from __future__ import annotations

__all__ = (
    "FilterDict",
    "LiteralFilterDict",
    "LogicalChildFilterDict",
    "LogicalChildrenFilterDict",
    "MultiPatternFilterDict",
    "OneOfFilterDict",
    "PatternFilterDict",
    "TemplateFilterDict",
    "WithoutFilterDict",
)

from typing import Any, NotRequired, TypedDict


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


class LiteralFilterDict(FilterDict):
    """Single-name enumerable filter dict (`LiteralFilter`)."""

    name: str


class OneOfFilterDict(FilterDict):
    """Explicit-set enumerable filter dict (`OneOfFilter`)."""

    names: list[str]


class TemplateFilterDict(FilterDict):
    """Cartesian-product enumerable filter dict (`TemplateFilter`).

    `axes` holds one list of values per format field; entries are
    heterogeneous (and only JSON scalars survive a round-trip), so they
    are typed as `Any`.
    """

    template: str
    axes: list[list[Any]]


class WithoutFilterDict(FilterDict):
    """Set-difference enumerable filter dict (`WithoutFilter`).

    `base` must deserialize to an `Expandable` filter; that constraint is
    enforced at construction, not by this shape (a `FilterDict` cannot
    express "an enumerable kind").
    """

    base: FilterDict
    excluded: list[FilterDict]

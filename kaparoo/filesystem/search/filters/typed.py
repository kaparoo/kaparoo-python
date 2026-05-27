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
    """Base TypedDict for any filter serialization; requires `kind`.

    All built-in family TypedDicts (`PatternFilterDict`,
    `MultiPatternFilterDict`, `LogicalChildrenFilterDict`,
    `LogicalChildFilterDict`) inherit from this base, adding their
    family-specific fields. User-defined filter dict types should
    likewise extend `FilterDict` to integrate type-safely with
    `Filter.parse` and the `search_*` wrappers.
    """

    kind: str


class PatternFilterDict(FilterDict):
    """Dict shape for `PatternFilter` subclasses (single string pattern).

    Mirrors the constructor signature of `EqualsFilter` and friends:
    a literal `pattern` plus an optional `case_sensitive` flag.
    """

    pattern: str
    case_sensitive: NotRequired[bool]


class MultiPatternFilterDict(FilterDict):
    """Dict shape for `MultiPatternFilter` subclasses (any-of patterns).

    Mirrors the constructor of `EqualsAnyFilter` and friends: a
    non-empty list of `patterns` plus an optional `case_sensitive`
    flag. Lists are JSON-friendly; the runtime `from_dict` converts
    them to `tuple` to match the dataclass field.
    """

    patterns: list[str]
    case_sensitive: NotRequired[bool]


class LogicalChildrenFilterDict(FilterDict):
    """Dict shape for `AndFilter` / `OrFilter` (multiple children)."""

    children: list[FilterDict]


class LogicalChildFilterDict(FilterDict):
    """Dict shape for `NotFilter` (a single child)."""

    child: FilterDict

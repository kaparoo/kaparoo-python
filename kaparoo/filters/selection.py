"""Select items by name against in-memory `include` / `exclude` filter specs.

This is the filesystem-agnostic base: it resolves specs that are already in
memory (a `str`, a `FilterDict`, a `Filter`, or a sequence of those) and never
touches the disk. Loading a spec from a `.json` / `.txt` file, and normalizing
subpath separators, live in `kaparoo.filesystem.search.selection`, which builds
on this module.
"""

from __future__ import annotations

__all__ = ("Selector", "resolve_selector", "select")

from typing import TYPE_CHECKING, cast

from kaparoo.filters.base import Filter
from kaparoo.filters.enumerable import Expandable, Literal, OneOf
from kaparoo.filters.logical import Or

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from kaparoo.filters.types import FilterDict


type NameFilter = str | FilterDict | Filter
type Selector = NameFilter | Sequence[NameFilter]


def _entry_filter(entry: NameFilter, normalize: Callable[[str], str] | None) -> Filter:
    """Turn one entry into a `Filter`.

    A `str` is an exact name (a `Literal`, with `normalize` applied when given);
    a mapping is a `FilterDict` (via `Filter.from_dict`); a `Filter` passes
    through.
    """
    if isinstance(entry, Filter):
        return entry
    if isinstance(entry, str):
        return Literal(normalize(entry) if normalize else entry)
    return Filter.from_dict(entry)


def _combine(
    entries: Sequence[NameFilter], normalize: Callable[[str], str] | None
) -> Filter | None:
    """Combine entries into one filter, `None` when there are none.

    An all-`str` list becomes an enumerable `OneOf` (so it stays typo-checked);
    any non-string entry drops the whole list to an OR of per-entry filters.
    """
    if not entries:
        return None

    strings = [entry for entry in entries if isinstance(entry, str)]
    if len(strings) == len(entries):
        names = [normalize(name) for name in strings] if normalize else strings
        return OneOf(names)

    filters = tuple(_entry_filter(entry, normalize) for entry in entries)
    return filters[0] if len(filters) == 1 else Or(filters)


def resolve_selector(
    selector: Selector | None, *, normalize: Callable[[str], str] | None = None
) -> Filter | None:
    """Normalize an in-memory selector spec into a filter, `None` for no restriction.

    The shared front end of `select`'s `include` / `exclude`, exposed so the
    two can be resolved -- and applied -- independently. `None` and an empty
    sequence both resolve to `None`.

    A `str` is a single exact name, a mapping is an inline `FilterDict`, a
    `Filter` passes through, and a sequence of entries (exact-name strings,
    `FilterDict`s, and / or `Filter`s) is OR-combined. `normalize`, when given,
    is applied to every exact-name string (an inline `str` or a string entry)
    before it becomes a `Literal` / `OneOf`; `FilterDict` patterns and
    `Filter`s are left untouched.

    `select`'s typo check (an exact name matching no item raises) lives in
    `select`, not here -- resolving a spec never inspects a collection.

    Raises:
        ValueError: If a `FilterDict` is malformed (unknown / missing `kind`).
    """
    if selector is None:
        return None
    if isinstance(selector, Filter):
        return selector
    if isinstance(selector, dict):
        return Filter.from_dict(cast("FilterDict", selector))
    if isinstance(selector, str):
        return Literal(normalize(selector) if normalize else selector)

    return _combine(list(selector), normalize)


def _ensure_all_present(label: str, spec: Filter | None, names: set[str]) -> None:
    """Raise if an enumerable `spec` names something absent from `names`.

    Only an `Expandable` filter (an exact-name set) can be checked this way; an
    open pattern (`Glob` / `Regex`) matching nothing is legitimate, so it is
    left unchecked.

    Raises:
        ValueError: If any enumerated name is not among `names`.
    """
    if isinstance(spec, Expandable) and (missing := sorted(set(spec.expand()) - names)):
        joined = ", ".join(missing)
        msg = f"{label} names no such item: {joined}"
        raise ValueError(msg)


def select[T](
    items: Iterable[T],
    *,
    key: Callable[[T], str],
    include: Selector | None = None,
    exclude: Selector | None = None,
    normalize: Callable[[str], str] | None = None,
) -> list[T]:
    """Keep the items `include` matches, then drop the ones `exclude` matches.

    Each item is named by `key`, then tested against two optional in-memory
    filter specs (see `resolve_selector` for the forms). An item survives when
    `include` matches it (or `include` is absent) **and** `exclude` does not --
    so on an overlap `exclude` wins. `normalize` is threaded into both specs'
    resolution.

    When a spec resolves to an enumerable set of names (a string, a string
    list, or an enumerable filter such as `OneOf`), a name matching no item
    raises -- a typo says so instead of silently selecting nothing. An open
    pattern (`Glob` / `Regex`) cannot be enumerated, so matching nothing is
    allowed.

    Args:
        items: The items to select from.
        key: The name to match an item by.
        include: The names / patterns to keep, or `None` for all of them.
        exclude: The names / patterns to drop, applied after `include`.
        normalize: Applied to every exact-name string before matching, or
            `None` to compare names verbatim.

    Returns:
        The surviving items, in the order `items` gave them.

    Raises:
        ValueError: If an exact-name spec names something no item holds, or a
            `FilterDict` is malformed (unknown / missing `kind`).
    """
    included = resolve_selector(include, normalize=normalize)
    excluded = resolve_selector(exclude, normalize=normalize)

    named = [(key(item), item) for item in items]
    names = {name for name, _ in named}

    _ensure_all_present("include", included, names)
    _ensure_all_present("exclude", excluded, names)

    return [
        item
        for name, item in named
        if (included is None or included.matches(name))
        and not (excluded is not None and excluded.matches(name))
    ]

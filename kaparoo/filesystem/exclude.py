from __future__ import annotations

__all__ = ("Excluder", "build_excluder")

from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, cast

from kaparoo.filters import Filter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from kaparoo.filesystem.types import StrPath


type Excluder = StrPath | Filter | Callable[[Path], bool]


def build_excluder(
    exclude: Excluder | Iterable[Excluder] | None, root: Path
) -> Callable[[Path], bool] | None:
    """Normalize `exclude` into a single exclusion predicate.

    The returned predicate relativizes a candidate path to `root` and excludes
    it when it matches *any* collected excluder -- a concrete path (exact match
    on the root-relative POSIX string), a `Filter` (matched on that string), or
    a callable (given the root-relative `Path`). It is the engine behind the
    `exclude=` argument of the `kaparoo.filesystem` traversals.

    Args:
        exclude: One excluder, an iterable of them (OR-combined), or `None`. An
            excluder is a root-relative `StrPath`, a `Filter`, or a callable; a
            lone `str` / `PathLike` / `Filter` / callable counts as one, while a
            non-string iterable is several.
        root: The base directory; every excluder and candidate is interpreted
            relative to it.

    Returns:
        A predicate mapping an absolute candidate path (assumed under `root`) to
        whether it is excluded, or `None` when nothing is excluded so callers
        can skip the check.
    """
    if exclude is None:
        return None

    exact: set[str] = set()
    filters: list[Filter] = []
    predicates: list[Callable[[Path], bool]] = []

    for excluder in _iter_excluders(exclude):
        if isinstance(excluder, str | PathLike):
            path = Path(cast("StrPath", excluder))
            exact.add(path.as_posix())
        elif isinstance(excluder, Filter):
            filters.append(excluder)
        else:
            predicates.append(excluder)

    if not (exact or filters or predicates):  # Nothing to exclude.
        return None

    def excluded(candidate: Path) -> bool:
        rel = candidate.relative_to(root)
        rel_str = rel.as_posix()

        if rel_str in exact:
            return True

        if any(f.matches(rel_str) for f in filters):
            return True

        return any(p(rel) for p in predicates)

    return excluded


def _iter_excluders(exclude: Excluder | Iterable[Excluder]) -> Iterator[Excluder]:
    """Yield each excluder; a lone `str` / `PathLike` / `Filter` / callable is one."""
    if isinstance(exclude, str | PathLike | Filter) or callable(exclude):
        yield cast("Excluder", exclude)
    else:
        yield from cast("Iterable[Excluder]", exclude)

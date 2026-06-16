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
    """Normalize `exclude` to one predicate over an absolute candidate path.

    The predicate relativizes the candidate to `root` and tests it against the
    collected concrete paths (set membership), `Filter`s (matched on the
    root-relative POSIX string), and callables (each given the root-relative
    `Path`). Returns `None` when nothing is excluded. Shared by the
    `kaparoo.filesystem` traversals that take an `exclude=` argument.
    """
    if exclude is None:
        return None

    relposix: set[str] = set()
    filters: list[Filter] = []
    predicates: list[Callable[[Path], bool]] = []
    for excluder in _iter_excluders(exclude):
        if isinstance(excluder, Filter):
            filters.append(excluder)
        elif isinstance(excluder, str | PathLike):
            relposix.add(Path(cast("StrPath", excluder)).as_posix())
        else:
            predicates.append(excluder)

    def excluded(candidate: Path) -> bool:
        rel = candidate.relative_to(root)
        relstr = rel.as_posix()
        return (
            relstr in relposix
            or any(f.matches(relstr) for f in filters)
            or any(p(rel) for p in predicates)
        )

    return excluded


def _iter_excluders(exclude: Excluder | Iterable[Excluder]) -> Iterator[Excluder]:
    """Yield each excluder; a lone `str` / `PathLike` / `Filter` / callable is one."""
    if isinstance(exclude, str | PathLike | Filter) or callable(exclude):
        yield cast("Excluder", exclude)
    else:
        yield from cast("Iterable[Excluder]", exclude)

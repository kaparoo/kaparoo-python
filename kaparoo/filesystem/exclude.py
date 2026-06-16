from __future__ import annotations

__all__ = ("ExcludeRule", "build_excluder")

from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, cast

from kaparoo.filters import Filter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from kaparoo.filesystem.types import StrPath


type ExcludeRule = StrPath | Filter | Callable[[Path], bool]


def build_excluder(
    exclude: ExcludeRule | Iterable[ExcludeRule] | None, root: Path
) -> Callable[[Path], bool] | None:
    """Normalize `exclude` into a single exclusion predicate.

    The returned predicate excludes a candidate path when it matches *any*
    collected rule -- a concrete path (exact match on the root-relative
    POSIX string), a `Filter` (matched on that string), or a callable (given
    the root-relative `Path`). A candidate under `root` is stripped to its
    root-relative part; any other relative candidate is taken to already be
    root-relative (an absolute candidate outside `root` is a caller error and
    raises `ValueError`). It is the engine behind the `exclude=` argument of
    the `kaparoo.filesystem` traversals.

    Args:
        exclude: One `ExcludeRule`, an iterable of them (OR-combined), or
            `None`. A rule is a root-relative `StrPath`, a `Filter`, or a
            callable; a lone `str` / `PathLike` / `Filter` / callable counts as
            one, while a non-string iterable is several.
        root: The base directory; every rule and candidate is interpreted
            relative to it.

    Returns:
        A predicate mapping a candidate path -- under `root`, or already
        root-relative -- to whether it is excluded, or `None` when nothing is
        excluded so callers can skip the check.
    """
    if exclude is None:
        return None

    exact: set[str] = set()
    filters: list[Filter] = []
    predicates: list[Callable[[Path], bool]] = []

    for rule in _iter_exclude_rules(exclude):
        if isinstance(rule, str | PathLike):
            path = Path(cast("StrPath", rule))
            exact.add(path.as_posix())
        elif isinstance(rule, Filter):
            filters.append(rule)
        else:
            predicates.append(rule)

    if not (exact or filters or predicates):  # Nothing to exclude.
        return None

    def excluder(candidate: Path) -> bool:
        rel = candidate

        try:
            rel = candidate.relative_to(root)
        except ValueError as error:
            if candidate.is_absolute():
                msg = f"absolute candidate {candidate!r} is outside the root {root!r}"
                raise ValueError(msg) from error

        rel_str = rel.as_posix()

        if rel_str in exact:
            return True

        if any(f.matches(rel_str) for f in filters):
            return True

        return any(p(rel) for p in predicates)

    return excluder


def _iter_exclude_rules(
    exclude: ExcludeRule | Iterable[ExcludeRule],
) -> Iterator[ExcludeRule]:
    """Yield each rule; a lone `str` / `PathLike` / `Filter` / callable is one."""
    if isinstance(exclude, str | PathLike | Filter) or callable(exclude):
        yield cast("ExcludeRule", exclude)
    else:
        yield from cast("Iterable[ExcludeRule]", exclude)

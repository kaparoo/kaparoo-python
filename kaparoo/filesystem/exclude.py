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
    collected rule. A path rule and the candidate are each reduced to a
    root-relative POSIX string (an absolute path under `root` stripped to its
    relative part, an already-relative one kept as-is), so a path rule matches
    by equality and a `Filter` matches that string. A *callable* rule instead
    receives the candidate's own `Path` -- the live, filesystem-valid path the
    traversal walks -- so it may inspect the file itself (size, contents,
    `iterdir`, ...), not just the name. An absolute path outside `root` (rule
    or candidate) is a caller error and raises `ValueError`. It is the engine
    behind the `exclude=` argument of the `kaparoo.filesystem` traversals.

    Args:
        exclude: One `ExcludeRule`, an iterable of them (OR-combined), or
            `None`. A rule is a `StrPath` (absolute under `root`, or
            root-relative), a `Filter`, or a callable on the candidate `Path`;
            a lone `str` / `PathLike` / `Filter` / callable counts as one,
            while a non-string iterable is several.
        root: The base directory; every rule and candidate is interpreted
            relative to it.

    Returns:
        A predicate from a candidate path (under `root`, or already
        root-relative) to whether it is excluded, or `None` when nothing is
        excluded so callers can skip the check.
    """
    if exclude is None:
        return None

    relpaths: set[str] = set()
    filters: list[Filter] = []
    predicates: list[Callable[[Path], bool]] = []

    for rule in _iter_exclude_rules(exclude):
        if isinstance(rule, str | PathLike):
            path = Path(cast("StrPath", rule))
            relpaths.add(_relativize(path, root).as_posix())
        elif isinstance(rule, Filter):
            filters.append(rule)
        else:
            predicates.append(rule)

    if not (relpaths or filters or predicates):  # Nothing to exclude.
        return None

    def excluder(path: Path) -> bool:
        relpath = _relativize(path, root).as_posix()

        return (
            relpath in relpaths
            or any(f.matches(relpath) for f in filters)
            or any(p(path) for p in predicates)
        )

    return excluder


def _relativize(path: Path, root: Path) -> Path:
    """Reduce `path` to its `root`-relative form.

    An absolute path under `root` is stripped to the relative part and an
    already-relative path is taken as already `root`-relative; an absolute
    path outside `root` is a caller error.

    Raises:
        ValueError: If `path` is an absolute path outside `root`.
    """
    try:
        return path.relative_to(root)
    except ValueError as error:
        if path.is_absolute():
            msg = f"{path!r} is not under the root {root!r}"
            raise ValueError(msg) from error
        return path


def _iter_exclude_rules(
    exclude: ExcludeRule | Iterable[ExcludeRule],
) -> Iterator[ExcludeRule]:
    """Yield each rule; a lone `str` / `PathLike` / `Filter` / callable is one."""
    if isinstance(exclude, str | PathLike | Filter) or callable(exclude):
        yield cast("ExcludeRule", exclude)
    else:
        yield from cast("Iterable[ExcludeRule]", exclude)

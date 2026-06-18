"""Low-level traversal helpers shared by `locate` and `validate`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from pathlib import Path

    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.hierarchy.entry import Entry


def _unique(pairs: Iterable[tuple[Path, Node]]) -> Iterator[tuple[Path, Node]]:
    """Stream `pairs`, suppressing ones already seen.

    Args:
        pairs: The `(path, node)` pairs to deduplicate.

    Yields:
        Each distinct pair in first-seen order (backed by a `seen` set).
    """
    seen: set[tuple[Path, Node]] = set()
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            yield pair


def _walk_depths(
    parent: Path, max_depth: int | None, excluder: Callable[[Path], bool] | None
) -> Iterator[tuple[Path, int]]:
    """Yield `(path, depth)` for every entry down to `max_depth` below `parent`.

    Uses `Path.walk` (iterative, like `search`), so depth is not bound by the
    recursion limit.

    Args:
        parent: The directory walked; a nonexistent or non-directory `parent`
            yields nothing.
        max_depth: The deepest level to descend, or `None` for no limit.
        excluder: A pre-built drop predicate, or `None`. Excluded entries are
            skipped and excluded directories pruned from the descent.

    Yields:
        `(path, depth)` for each non-excluded entry, `depth` counted from 1 at
        `parent`'s direct children.
    """
    has_max_depth = max_depth is not None
    has_excluder = excluder is not None

    parent_depth = len(parent.parts)

    for dirpath, dirnames, filenames in parent.walk():
        depth = len(dirpath.parts) - parent_depth + 1

        excluded: set[str] = set()

        for name in sorted((*dirnames, *filenames)):
            candidate = dirpath / name

            if has_excluder and excluder(candidate):
                excluded.add(name)
                continue

            yield (candidate, depth)

        if excluded:
            dirnames[:] = [d for d in dirnames if d not in excluded]

        if has_max_depth and depth >= max_depth:
            dirnames.clear()  # prune deeper levels (Path.walk honors the edit)


def _entry_accepts(entry: Entry, candidate: Path, depth: int) -> bool:
    """Whether `entry` accepts `candidate` at `depth`.

    Adds the positional `accepts_depth` gate to `entry.matches` (name + kind) --
    the single source of the gates shared by `locate` and `validate`, run
    cheapest-first: the in-memory `depth` and name checks before `accepts_kind`,
    which stats the path.

    Args:
        entry: The spec entry to test.
        candidate: The on-disk path the walk discovered.
        depth: `candidate`'s depth below the walked parent (1-based).
    """
    return entry.accepts_depth(depth) and entry.matches(candidate)

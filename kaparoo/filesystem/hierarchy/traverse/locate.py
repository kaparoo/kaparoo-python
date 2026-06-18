"""Locate where a hierarchy spec appears in a real directory tree (`locate`)."""

from __future__ import annotations

__all__ = ("locate", "locate_map")

from pathlib import Path
from typing import TYPE_CHECKING, cast

from kaparoo.filesystem.exclude import build_excluder
from kaparoo.filesystem.hierarchy.entry import Directory
from kaparoo.filesystem.hierarchy.group import Group, flatten_entries, max_depth_of
from kaparoo.filesystem.hierarchy.traverse._utils import (
    _entry_accepts,
    _unique,
    _walk_depths,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from kaparoo.filesystem.exclude import ExcludeRule
    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.hierarchy.entry import Entry
    from kaparoo.filesystem.types import StrPath


def locate(
    tree: Node,
    root: StrPath,
    *,
    unique: bool = False,
    exclude: ExcludeRule | Iterable[ExcludeRule] | None = None,
    root_as_top: bool = False,
) -> Iterator[tuple[Path, Node]]:
    """Yield each on-disk path under `root` paired with the node it matches.

    By default `root` is the *container* and `tree`'s top is matched as an
    entry beneath it (like `search`'s `root`). A path matches a node by name
    (the node's filter), kind (`File` <-> file, `Directory` <-> directory),
    and `depth` (intermediate levels of unknown name are skipped); a path
    matching several nodes yields one pair each. Only what is *present* is
    reported -- a `Group` counts as "any of its entries may appear", leaving
    missing `required` and `Exclusive` / `Together` checks to `validate`. A
    nonexistent or non-directory `root` yields nothing.

    Args:
        tree: The spec whose top node anchors the match.
        root: The directory walked for matches; the realized top itself when
            `root_as_top`.
        unique: Suppress duplicate `(path, node)` pairs (a reused subtree
            otherwise repeats once per occurrence); iteration stays lazy.
        exclude: Path(s) to drop -- a `StrPath` (absolute under `root` or
            root-relative), a `Filter` (on the root-relative POSIX path), a
            callable on the candidate's real `Path`, or an iterable of these
            (OR-combined). A dropped directory is pruned whole.
        root_as_top: Treat `root` *itself* as the realized top rather than its
            container; the top must be an `Entry`, realized only when `root`'s
            leaf name and kind match it.

    Yields:
        `(path, node)` in depth-first order, a path's overlapping nodes in
        spec order.

    Raises:
        TypeError: If `root_as_top` and `tree`'s top is a `Group`.
    """
    root = Path(root)
    excluder = build_excluder(exclude, root)
    worker = _locate_as_top if root_as_top else _locate_under
    pairs = worker(tree, root, excluder)
    yield from _unique(pairs) if unique else pairs


def locate_map(
    tree: Node,
    root: StrPath,
    *,
    exclude: ExcludeRule | Iterable[ExcludeRule] | None = None,
) -> dict[Path, tuple[Node, ...]]:
    """Group `locate`'s pairs into a `{path: (node, ...)}` mapping.

    Unlike `locate`, the full result is materialized before returning.

    Args:
        tree: The spec whose top node anchors the match.
        root: The directory walked for matches.
        exclude: Path(s) to drop, as in `locate`.

    Returns:
        Each on-disk path mapped to the distinct nodes it matches, in spec
        order.
    """
    root = Path(root)
    excluder = build_excluder(exclude, root)
    return _locate_map(tree, root, excluder)


def _locate_map(
    tree: Node, root: Path, excluder: Callable[[Path], bool] | None
) -> dict[Path, tuple[Node, ...]]:
    """Group located pairs over a pre-built `excluder` (core of `locate_map`).

    Args:
        tree: The spec whose top node anchors the match.
        root: The directory walked for matches.
        excluder: A pre-built drop predicate, or `None` to exclude nothing.

    Returns:
        Each path mapped to the distinct nodes it matches, in spec order.
    """
    grouped: dict[Path, list[Node]] = {}

    for path, node in _unique(_locate_under(tree, root, excluder)):
        grouped.setdefault(path, []).append(node)

    return {path: tuple(nodes) for path, nodes in grouped.items()}


def _locate_as_top(
    top: Node, root: Path, excluder: Callable[[Path], bool] | None
) -> Iterator[tuple[Path, Node]]:
    """Match `top` as `root` itself rather than a child of a container.

    Args:
        top: The spec's top node; must be an `Entry`.
        root: The path tested as the realized `top`.
        excluder: A pre-built drop predicate, or `None` to exclude nothing.

    Yields:
        The `(root, top)` pair when `root`'s leaf name and kind match `top`,
        then a `Directory`'s located children; nothing on a mismatch.

    Raises:
        TypeError: If `top` is a `Group` (it has no single name to anchor).
    """
    if isinstance(top, Group):
        msg = "root_as_top requires an Entry top node, not a Group"
        raise TypeError(msg)

    entry = cast("Entry", top)

    if not (entry.name.matches(root.name) and entry.accepts_kind(root)):
        return

    yield (root, entry)

    if isinstance(entry, Directory):
        yield from _locate_under(entry.children, root, excluder)


def _locate_under(
    nodes: Node | Iterable[Node], parent: Path, excluder: Callable[[Path], bool] | None
) -> Iterator[tuple[Path, Node]]:
    """Locate `nodes` as entries under `parent`, against one walk of `parent`.

    Groups flatten to leaf entries (matched as siblings); `parent` is walked
    once, deep enough for the deepest entry, and a matched `Directory`
    recurses into its children.

    Args:
        nodes: The sibling node(s) expected directly under `parent`.
        parent: The directory walked for matches.
        excluder: A pre-built drop predicate, or `None`. Dropped directories
            are pruned from the walk.

    Yields:
        `(path, entry)` for each entry whose depth, name, and kind match a
        walked path.
    """
    entries = flatten_entries(nodes)
    if not entries:
        return

    for candidate, depth in _walk_depths(parent, max_depth_of(entries), excluder):
        for entry in entries:
            if _entry_accepts(entry, candidate, depth):
                yield (candidate, entry)

                if isinstance(entry, Directory):
                    yield from _locate_under(entry.children, candidate, excluder)

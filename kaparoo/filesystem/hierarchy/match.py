from __future__ import annotations

__all__ = ("match", "match_map")

from pathlib import Path
from typing import TYPE_CHECKING, cast

from kaparoo.filesystem.hierarchy.entry import Directory, File
from kaparoo.filesystem.hierarchy.group import Group

if TYPE_CHECKING:
    from collections.abc import Iterator

    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.hierarchy.entry import Entry
    from kaparoo.filesystem.types import StrPath


def match(
    tree: Node, root: StrPath, *, unique: bool = False
) -> Iterator[tuple[Path, Node]]:
    """Map each path under `root` to the spec `tree` node(s) it matches.

    `root` is the *container*: `tree`'s top node is matched as an entry
    under `root` (mirroring `search`'s `root`). For every on-disk path that
    matches a node -- by name (the node's filter), type (`File` <-> file,
    `Directory` <-> directory), and `depth` (intermediate levels of unknown
    name are skipped) -- a `(path, node)` pair is yielded. A path matching
    several nodes yields one pair per node.

    `match` reports only what is *present*: missing `required` entries and
    `Exclusive` / `Together` violations are `validate`'s concern, so a
    `Group` here is treated as "any of its entries may appear." A
    nonexistent or non-directory `root` simply yields nothing.

    Args:
        unique: When `False` (default) the same `(path, node)` pair may
            repeat (a reused subtree shows up once per occurrence) and
            iteration stays lazy. When `True`, duplicate pairs are
            suppressed (still streamed, backed by a `seen` set).

    Yields:
        `(path, node)` for each match, in spec-traversal order.
    """
    pairs = _match_under(tree, Path(root))
    if not unique:
        yield from pairs
        return
    seen: set[tuple[Path, Node]] = set()
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            yield pair


def match_map(tree: Node, root: StrPath) -> dict[Path, tuple[Node, ...]]:
    """Group `match` results into a `path -> matching nodes` mapping.

    Each on-disk path maps to the tuple of distinct nodes it matches, in
    spec-traversal order (so overlapping nodes for one path are collected
    rather than yielded separately). Unlike `match`, this materializes the
    full result before returning. Iterate `.items()` for `(path, nodes)`
    pairs; index by path to look a single one up.
    """
    grouped: dict[Path, list[Node]] = {}
    for path, node in match(tree, root, unique=True):
        grouped.setdefault(path, []).append(node)
    return {path: tuple(nodes) for path, nodes in grouped.items()}


def _match_under(node: Node, parent: Path) -> Iterator[tuple[Path, Node]]:
    if isinstance(node, Group):
        for entry in node.entries:
            yield from _match_under(entry, parent)
        return

    entry = cast("Entry", node)
    for path in _at_depths(parent, entry.min_depth, entry.max_depth):
        if not entry.name.matches(path.name) or not _type_ok(entry, path):
            continue
        yield (path, entry)
        if isinstance(entry, Directory):
            for child in entry.children:
                yield from _match_under(child, path)


def _type_ok(entry: Entry, path: Path) -> bool:
    """Whether `path`'s kind matches the entry's (file vs directory)."""
    if isinstance(entry, File):
        return path.is_file()
    return path.is_dir()


def _at_depths(parent: Path, min_depth: int, max_depth: int | None) -> Iterator[Path]:
    """Yield entries `min_depth..max_depth` levels below `parent`.

    Levels above a yielded entry are unconstrained directories. Built on
    `Path.walk` (iterative, like `search`) rather than Python recursion, so
    arbitrarily deep trees never hit the recursion limit; a nonexistent or
    non-directory `parent` yields nothing (walk errors are ignored).
    """
    parent_depth = len(parent.parts)
    for dirpath, dirnames, filenames in parent.walk():
        child_depth = len(dirpath.parts) - parent_depth + 1
        if child_depth >= min_depth:
            for name in sorted((*dirnames, *filenames)):
                yield dirpath / name
        if max_depth is not None and child_depth >= max_depth:
            dirnames.clear()  # prune deeper levels (Path.walk honors the edit)

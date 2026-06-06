from __future__ import annotations

__all__ = ("match", "match_map")

from pathlib import Path
from typing import TYPE_CHECKING

from kaparoo.filesystem.hierarchy.entry import Directory, File
from kaparoo.filesystem.hierarchy.group import flatten_entries

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

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
        `(path, node)` for each match -- paths in depth-first directory
        order, a path's overlapping nodes in spec order.
    """
    pairs = _match_children((tree,), Path(root))
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

    Each on-disk path maps to the tuple of distinct nodes it matches (in
    spec order), so overlapping nodes for one path are collected rather than
    yielded separately. Unlike `match`, this materializes the full result
    before returning. Iterate `.items()` for `(path, nodes)` pairs, or index
    by path to look a single one up.
    """
    grouped: dict[Path, list[Node]] = {}
    for path, node in match(tree, root, unique=True):
        grouped.setdefault(path, []).append(node)
    return {path: tuple(nodes) for path, nodes in grouped.items()}


def _match_children(nodes: Iterable[Node], parent: Path) -> Iterator[tuple[Path, Node]]:
    """Match the sibling entries of `nodes` against one walk of `parent`.

    Groups flatten to their leaf entries (matched as siblings). `parent` is
    walked a single time, deep enough for the deepest entry; each discovered
    path is tested against every entry whose depth range admits it, and a
    matched directory recurses into its own children.
    """
    entries = flatten_entries(nodes)
    if not entries:
        return
    for candidate, depth in _walk_depths(parent, _max_depth(entries)):
        for entry in entries:
            if (
                _depth_ok(entry, depth)
                and entry.name.matches(candidate.name)
                and _type_ok(entry, candidate)
            ):
                yield (candidate, entry)
                if isinstance(entry, Directory):
                    yield from _match_children(entry.children, candidate)


def _type_ok(entry: Entry, path: Path) -> bool:
    """Whether `path`'s kind matches the entry's (file vs directory)."""
    if isinstance(entry, File):
        return path.is_file()
    return path.is_dir()


def _depth_ok(entry: Entry, depth: int) -> bool:
    """Whether `depth` falls in the entry's inclusive depth range."""
    return entry.min_depth <= depth and (
        entry.max_depth is None or depth <= entry.max_depth
    )


def _max_depth(entries: tuple[Entry, ...]) -> int | None:
    """The deepest level any entry needs (`None` if any is unbounded)."""
    bound = 1
    for entry in entries:
        if entry.max_depth is None:
            return None
        bound = max(bound, entry.max_depth)
    return bound


def _walk_depths(parent: Path, max_depth: int | None) -> Iterator[tuple[Path, int]]:
    """Yield `(path, depth)` for entries down to `max_depth` below `parent`.

    Built on `Path.walk` (iterative, like `search`) rather than Python
    recursion, so arbitrarily deep trees never hit the recursion limit; a
    nonexistent or non-directory `parent` yields nothing (walk errors are
    ignored).
    """
    parent_depth = len(parent.parts)
    for dirpath, dirnames, filenames in parent.walk():
        depth = len(dirpath.parts) - parent_depth + 1
        for name in sorted((*dirnames, *filenames)):
            yield (dirpath / name, depth)
        if max_depth is not None and depth >= max_depth:
            dirnames.clear()  # prune deeper levels (Path.walk honors the edit)

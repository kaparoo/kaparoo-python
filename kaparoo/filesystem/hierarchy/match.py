from __future__ import annotations

__all__ = ("match",)

from pathlib import Path
from typing import TYPE_CHECKING, cast

from kaparoo.filesystem.hierarchy.entry import Directory, File
from kaparoo.filesystem.hierarchy.group import Group

if TYPE_CHECKING:
    from collections.abc import Iterator

    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.hierarchy.entry import Entry
    from kaparoo.filesystem.types import StrPath


def match(tree: Node, root: StrPath) -> Iterator[tuple[Path, Node]]:
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
    """
    yield from _match_under(tree, Path(root))


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

    Levels above a yielded entry are unconstrained directories.
    """

    def walk(directory: Path, depth: int) -> Iterator[Path]:
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if depth >= min_depth:
                yield entry
            if entry.is_dir() and (max_depth is None or depth < max_depth):
                yield from walk(entry, depth + 1)

    yield from walk(parent, 1)

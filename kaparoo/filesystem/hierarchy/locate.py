from __future__ import annotations

__all__ = ("locate", "locate_map")

from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, cast

from kaparoo.filesystem.hierarchy.entry import Directory, File
from kaparoo.filesystem.hierarchy.group import Group, flatten_entries

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.hierarchy.entry import Entry
    from kaparoo.filesystem.types import StrPath


type Excluder = StrPath | Callable[[Path], bool]


def locate(
    tree: Node,
    root: StrPath,
    *,
    unique: bool = False,
    exclude: Excluder | Iterable[Excluder] | None = None,
    at_root: bool = False,
) -> Iterator[tuple[Path, Node]]:
    """Map each path under `root` to the spec `tree` node(s) it matches.

    By default `root` is the *container*: `tree`'s top node is matched as an
    entry under `root` (mirroring `search`'s `root`). For every on-disk path
    that matches a node -- by name (the node's filter), type (`File` <-> file,
    `Directory` <-> directory), and `depth` (intermediate levels of unknown
    name are skipped) -- a `(path, node)` pair is yielded. A path matching
    several nodes yields one pair per node.

    `locate` reports only what is *present*: missing `required` entries and
    `Exclusive` / `Together` violations are `validate`'s concern, so a
    `Group` here is treated as "any of its entries may appear." A
    nonexistent or non-directory `root` simply yields nothing.

    Args:
        unique: When `False` (default) the same `(path, node)` pair may
            repeat (a reused subtree shows up once per occurrence) and
            iteration stays lazy. When `True`, duplicate pairs are
            suppressed (still streamed, backed by a `seen` set).
        exclude: Paths to drop from the results -- e.g. specific cells of a
            `Template` product. An excluder (or an iterable of them,
            OR-combined) is either a `StrPath` (a concrete **root-relative**
            path) or a `Callable` taking the **root-relative** `Path` and
            returning whether to drop it. A dropped directory has its whole
            subtree pruned. A lone `str` / `PathLike` / callable is one
            excluder; only a non-string iterable is several.
        at_root: When `True`, treat `root` *itself* as the realized top node
            rather than its container -- so you point at the top directly
            (`locate(Directory("dataset", ...), ".../dataset", at_root=True)`).
            The top must be an `Entry` (a `Group` raises `ValueError`); `root`
            realizes it only when `root`'s leaf name matches the top's name
            filter and its kind agrees, otherwise nothing is yielded.

    Yields:
        `(path, node)` for each match -- paths in depth-first directory
        order, a path's overlapping nodes in spec order.

    Raises:
        TypeError: If `at_root` is set and `tree`'s top node is a `Group`.
    """
    root_path = Path(root)
    excluded = build_excluder(exclude, root_path)
    pairs = (
        _locate_at_root(tree, root_path, excluded)
        if at_root
        else _locate_children((tree,), root_path, excluded)
    )

    if not unique:
        yield from pairs
        return

    seen: set[tuple[Path, Node]] = set()
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            yield pair


def _locate_at_root(
    top: Node, root_path: Path, excluded: Callable[[Path], bool] | None
) -> Iterator[tuple[Path, Node]]:
    """Match `top` as `root_path` itself, not as a child of a container.

    The `at_root` form of `_locate_children`: `root_path` realizes `top` only
    when its leaf name matches `top`'s name filter and its kind agrees, in
    which case the top pair is yielded and a `Directory`'s children are
    located beneath `root_path`. A name / kind mismatch yields nothing.

    Raises:
        TypeError: If `top` is a `Group` (it has no single name to anchor).
    """
    if isinstance(top, Group):
        msg = "at_root requires an Entry top node, not a Group"
        raise TypeError(msg)

    entry = cast("Entry", top)
    if not (entry.name.matches(root_path.name) and _type_ok(entry, root_path)):
        return

    yield (root_path, entry)
    if isinstance(entry, Directory):
        yield from _locate_children(entry.children, root_path, excluded)


def locate_map(
    tree: Node,
    root: StrPath,
    *,
    exclude: Excluder | Iterable[Excluder] | None = None,
) -> dict[Path, tuple[Node, ...]]:
    """Group `locate` results into a `path -> matching nodes` mapping.

    Each on-disk path maps to the tuple of distinct nodes it matches (in
    spec order), so overlapping nodes for one path are collected rather than
    yielded separately. Unlike `locate`, this materializes the full result
    before returning. Iterate `.items()` for `(path, nodes)` pairs, or index
    by path to look a single one up. `exclude` is as in `locate`.
    """
    grouped: dict[Path, list[Node]] = {}
    for path, node in locate(tree, root, unique=True, exclude=exclude):
        grouped.setdefault(path, []).append(node)
    return {path: tuple(nodes) for path, nodes in grouped.items()}


def build_excluder(
    exclude: Excluder | Iterable[Excluder] | None, root: Path
) -> Callable[[Path], bool] | None:
    """Normalize `exclude` to one predicate over an absolute candidate path.

    The predicate relativizes the candidate to `root` and tests it against
    the collected concrete paths (set membership) and callables (each given
    the root-relative `Path`). Returns `None` when nothing is excluded.
    Shared with `validate`, which reuses it to skip excluded paths.
    """
    if exclude is None:
        return None

    relposix: set[str] = set()
    predicates: list[Callable[[Path], bool]] = []
    for excluder in _iter_excluders(exclude):
        if isinstance(excluder, str | PathLike):
            relposix.add(Path(cast("StrPath", excluder)).as_posix())
        else:
            predicates.append(excluder)

    def excluded(candidate: Path) -> bool:
        rel = candidate.relative_to(root)
        return rel.as_posix() in relposix or any(p(rel) for p in predicates)

    return excluded


def _iter_excluders(exclude: Excluder | Iterable[Excluder]) -> Iterator[Excluder]:
    """Yield each excluder; a lone `str` / `PathLike` / callable is one."""
    if isinstance(exclude, str | PathLike) or callable(exclude):
        yield cast("Excluder", exclude)
    else:
        yield from cast("Iterable[Excluder]", exclude)


def _locate_children(
    nodes: Iterable[Node], parent: Path, excluded: Callable[[Path], bool] | None
) -> Iterator[tuple[Path, Node]]:
    """Locate the sibling entries of `nodes` against one walk of `parent`.

    Groups flatten to their leaf entries (matched as siblings). `parent` is
    walked a single time, deep enough for the deepest entry; each discovered
    path is tested against every entry whose depth range admits it, and a
    matched directory recurses into its own children. `excluded` paths are
    dropped (and pruned if directories) during the walk.
    """
    entries = flatten_entries(nodes)
    if not entries:
        return
    for candidate, depth in _walk_depths(parent, _max_depth(entries), excluded):
        for entry in entries:
            if (
                _depth_ok(entry, depth)
                and entry.name.matches(candidate.name)
                and _type_ok(entry, candidate)
            ):
                yield (candidate, entry)
                if isinstance(entry, Directory):
                    yield from _locate_children(entry.children, candidate, excluded)


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


def _walk_depths(
    parent: Path, max_depth: int | None, excluded: Callable[[Path], bool] | None
) -> Iterator[tuple[Path, int]]:
    """Yield `(path, depth)` for entries down to `max_depth` below `parent`.

    Built on `Path.walk` (iterative, like `search`) rather than Python
    recursion, so arbitrarily deep trees never hit the recursion limit; a
    nonexistent or non-directory `parent` yields nothing (walk errors are
    ignored). `excluded` entries are skipped, and excluded directories are
    pruned from the descent.
    """
    parent_depth = len(parent.parts)
    for dirpath, dirnames, filenames in parent.walk():
        depth = len(dirpath.parts) - parent_depth + 1
        for name in sorted((*dirnames, *filenames)):
            candidate = dirpath / name
            if excluded is not None and excluded(candidate):
                continue
            yield (candidate, depth)
        if excluded is not None:
            dirnames[:] = [d for d in dirnames if not excluded(dirpath / d)]
        if max_depth is not None and depth >= max_depth:
            dirnames.clear()  # prune deeper levels (Path.walk honors the edit)

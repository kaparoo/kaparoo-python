from __future__ import annotations

__all__ = (
    "ValidationReport",
    "Violation",
    "conforms",
    "locate",
    "locate_map",
    "validate",
)

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from kaparoo.filesystem.exclude import build_excluder
from kaparoo.filesystem.hierarchy.conditions import CheckContext
from kaparoo.filesystem.hierarchy.entry import Directory, Entry, File
from kaparoo.filesystem.hierarchy.group import (
    Exclusive,
    Group,
    Together,
    flatten_entries,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

    from kaparoo.filesystem.exclude import Excluder
    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.types import StrPath

    type ContentChecks = Mapping[str, Callable[[Path], bool]]


_NO_CHECKS = CheckContext()


# ========================== #
#           Locate           #
# ========================== #


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
            OR-combined) is a `StrPath` (a concrete **root-relative** path), a
            `Filter` (matched on the **root-relative** POSIX string), or a
            `Callable` taking the **root-relative** `Path` and returning
            whether to drop it. A dropped directory has its whole subtree
            pruned. A lone `str` / `PathLike` / `Filter` / callable is one
            excluder; only a non-string iterable is several.
        at_root: When `True`, treat `root` *itself* as the realized top node
            rather than its container -- so you point at the top directly
            (`locate(Directory("dataset", ...), ".../dataset", at_root=True)`).
            The top must be an `Entry` (a `Group` raises `TypeError`); `root`
            realizes it only when `root`'s leaf name matches the top's name
            filter and its kind agrees, otherwise nothing is yielded.

    Yields:
        `(path, node)` for each match -- paths in depth-first directory
        order, a path's overlapping nodes in spec order.

    Raises:
        TypeError: If `at_root` is set and `tree`'s top node is a `Group`.
    """
    root_path = Path(root)
    excluder = build_excluder(exclude, root_path)
    pairs = (
        _locate_at_root(tree, root_path, excluder)
        if at_root
        else _locate_children((tree,), root_path, excluder)
    )

    yield from _unique(pairs) if unique else pairs


def _unique(
    pairs: Iterable[tuple[Path, Node]],
) -> Iterator[tuple[Path, Node]]:
    """Stream `pairs`, suppressing ones already seen (backed by a `set`)."""
    seen: set[tuple[Path, Node]] = set()
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            yield pair


def _locate_at_root(
    top: Node, root_path: Path, excluder: Callable[[Path], bool] | None
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
        yield from _locate_children(entry.children, root_path, excluder)


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
    root_path = Path(root)
    return _locate_map(tree, root_path, build_excluder(exclude, root_path))


def _locate_map(
    tree: Node, root_path: Path, excluder: Callable[[Path], bool] | None
) -> dict[Path, tuple[Node, ...]]:
    """`locate_map`'s core over a pre-built `excluder` predicate.

    `validate` reuses this so it can build the excluder once and share it
    across every top node, rather than rebuilding it on each `locate_map`
    call.
    """
    grouped: dict[Path, list[Node]] = {}
    for path, node in _unique(_locate_children((tree,), root_path, excluder)):
        grouped.setdefault(path, []).append(node)
    return {path: tuple(nodes) for path, nodes in grouped.items()}


def _locate_children(
    nodes: Iterable[Node], parent: Path, excluder: Callable[[Path], bool] | None
) -> Iterator[tuple[Path, Node]]:
    """Locate the sibling entries of `nodes` against one walk of `parent`.

    Groups flatten to their leaf entries (matched as siblings). `parent` is
    walked a single time, deep enough for the deepest entry; each discovered
    path is tested against every entry whose depth range admits it, and a
    matched directory recurses into its own children. Excluded paths are
    dropped (and pruned if directories) during the walk.
    """
    entries = flatten_entries(nodes)
    if not entries:
        return
    for candidate, depth in _walk_depths(parent, _max_depth(entries), excluder):
        for entry in entries:
            if (
                _depth_ok(entry, depth)
                and entry.name.matches(candidate.name)
                and _type_ok(entry, candidate)
            ):
                yield (candidate, entry)
                if isinstance(entry, Directory):
                    yield from _locate_children(entry.children, candidate, excluder)


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
    parent: Path, max_depth: int | None, excluder: Callable[[Path], bool] | None
) -> Iterator[tuple[Path, int]]:
    """Yield `(path, depth)` for entries down to `max_depth` below `parent`.

    Built on `Path.walk` (iterative, like `search`) rather than Python
    recursion, so arbitrarily deep trees never hit the recursion limit; a
    nonexistent or non-directory `parent` yields nothing (walk errors are
    ignored). Excluded entries are skipped, and excluded directories are
    pruned from the descent.
    """
    parent_depth = len(parent.parts)
    for dirpath, dirnames, filenames in parent.walk():
        depth = len(dirpath.parts) - parent_depth + 1
        for name in sorted((*dirnames, *filenames)):
            candidate = dirpath / name
            if excluder is not None and excluder(candidate):
                continue
            yield (candidate, depth)
        if excluder is not None:
            dirnames[:] = [d for d in dirnames if not excluder(dirpath / d)]
        if max_depth is not None and depth >= max_depth:
            dirnames.clear()  # prune deeper levels (Path.walk honors the edit)


# ========================== #
#          Validate          #
# ========================== #


@dataclass(frozen=True)
class Violation:
    """A constraint that a matched tree breaks.

    `kind` is the group's type, `node` the offending `Exclusive` /
    `Together`, and `present` the leaf entries found present: for
    `exclusive`, the entries across the more-than-one sides that coexist;
    for `together`, the members present while others are absent.
    """

    kind: Literal["exclusive", "together"]
    node: Group
    present: tuple[Entry, ...]


@dataclass(frozen=True)
class ValidationReport:
    """The outcome of checking a real directory against a spec tree.

    `matched` maps each on-disk path to the node(s) it matched (exactly
    `locate_map`); `unexpected` are paths matching no node; `missing` are
    `required` entries / groups left unsatisfied; `violations` are broken
    `Exclusive` / `Together` constraints; `failed` are `(path, node)` pairs
    where the matched path broke the node's attribute `condition`. `ok` --
    and the report's truthiness -- is `True` only when `unexpected`,
    `missing`, `violations`, and `failed` are all empty.
    """

    matched: dict[Path, tuple[Node, ...]]
    unexpected: tuple[Path, ...]
    missing: tuple[Node, ...]
    violations: tuple[Violation, ...]
    failed: tuple[tuple[Path, Node], ...]

    @property
    def ok(self) -> bool:
        return not (self.unexpected or self.missing or self.violations or self.failed)

    def __bool__(self) -> bool:
        return self.ok


def validate(
    tree: Node,
    root: StrPath,
    *,
    exclude: Excluder | Iterable[Excluder] | None = None,
    checks: ContentChecks | None = None,
    on_missing: Literal["error", "skip"] = "error",
    at_root: bool = False,
) -> ValidationReport:
    """Check the directory at `root` against the spec `tree`.

    By default `root` is the container (as in `locate`); returns a
    `ValidationReport`. A path is `unexpected` when it is neither matched nor
    an ancestor of a match, so an unspecified directory's contents count too.
    A `required` entry is satisfied as soon as its name matches one present
    path -- for an enumerable name (`OneOf` / `Template`) that means *at least
    one* of the listed names exists, not all. `exclude` is as in `locate`:
    excluded paths are dropped from `matched` and not reported `unexpected` (a
    dropped directory is pruned).

    An entry's attribute `condition` is checked on each matched path and the
    failures collected in `report.failed`. `checks` supplies the callables
    for `Content` conditions (keyed by name); `on_missing` decides what
    happens when a `Content` name is absent (`"error"` raises, `"skip"`
    treats it as satisfied).

    Args:
        at_root: When `True`, treat `root` *itself* as the realized top node
            rather than its container, so you point at the top directly. The
            top must be an `Entry` (a `Group` raises `TypeError`); when
            `root`'s leaf name / kind do not realize it, the top is reported
            `missing` and its subtree is not descended.

    Raises:
        TypeError: If `at_root` is set and `tree`'s top node is a `Group`.
    """
    ctx = CheckContext(checks or {}, on_missing)
    root_path = Path(root)
    if at_root:
        return _validate_at_root(tree, root_path, exclude, ctx)

    return _build_report((tree,), root_path, exclude, ctx)


def _validate_at_root(
    top: Node,
    root_path: Path,
    exclude: Excluder | Iterable[Excluder] | None,
    ctx: CheckContext,
) -> ValidationReport:
    """Validate `root_path` as the realized top entry, not as a container.

    The `at_root` form of `_build_report`. When `root_path` does not realize
    `top` (leaf name / kind mismatch) the top is reported `missing` and the
    subtree is not descended; otherwise the directory's children are validated
    beneath `root_path` and the top's own `condition` is checked on it.

    Raises:
        TypeError: If `top` is a `Group` (it has no single name to anchor).
    """
    if isinstance(top, Group):
        msg = "at_root requires an Entry top node, not a Group"
        raise TypeError(msg)

    entry = cast("Entry", top)
    if not (entry.name.matches(root_path.name) and _type_ok(entry, root_path)):
        return ValidationReport({}, (), (entry,), (), ())

    if isinstance(entry, File):
        failed = _failed_condition(entry, root_path, ctx)
        return ValidationReport({root_path: (entry,)}, (), (), (), failed)

    directory = cast("Directory", entry)
    report = _build_report(directory.children, root_path, exclude, ctx)
    return ValidationReport(
        matched={root_path: (entry,), **report.matched},
        unexpected=report.unexpected,
        missing=report.missing,
        violations=report.violations,
        failed=report.failed + _failed_condition(entry, root_path, ctx),
    )


def _failed_condition(
    entry: Entry, path: Path, ctx: CheckContext
) -> tuple[tuple[Path, Node], ...]:
    """The `(path, entry)` failure tuple if `entry`'s condition breaks, else empty."""
    if entry.condition is not None and not entry.condition.check(path, ctx):
        return ((path, entry),)

    return ()


def _build_report(
    top_nodes: tuple[Node, ...],
    root_path: Path,
    exclude: Excluder | Iterable[Excluder] | None = None,
    ctx: CheckContext = _NO_CHECKS,
) -> ValidationReport:
    """Validate `top_nodes` matched directly under `root_path`.

    The `exclude` predicate is built once here and threaded into both the
    match phase (`_merge_matched`) and the `_unexpected` sweep, rather than
    rebuilt per top node.
    """
    excluder = build_excluder(exclude, root_path)
    matched = _merge_matched(top_nodes, root_path, excluder)
    present: set[Node] = {node for nodes in matched.values() for node in nodes}

    missing: list[Node] = []
    violations: list[Violation] = []
    demoted: set[int] = set()
    for top in top_nodes:
        for node in _walk_nodes(top):
            if id(node) in demoted:
                continue  # under a priority Exclusive's losing side
            if isinstance(node, Entry):
                if node.required and node not in present:
                    missing.append(node)
            else:
                group = cast("Group", node)
                violation, group_missing, group_demoted = _check_group(group, present)
                if violation is not None:
                    violations.append(violation)
                if group_missing:
                    missing.append(group)
                demoted.update(id(n) for n in group_demoted)

    if demoted:
        # Drop the resolved-away nodes so their paths fall through to
        # `unexpected`; identity-keyed, as nodes compare by value.
        matched = {
            path: kept
            for path, nodes in matched.items()
            if (kept := tuple(n for n in nodes if id(n) not in demoted))
        }

    failed = tuple(
        (path, node)
        for path, nodes in matched.items()
        for node in nodes
        if isinstance(node, Entry)
        and node.condition is not None
        and not node.condition.check(path, ctx)
    )

    return ValidationReport(
        matched=matched,
        unexpected=tuple(_unexpected(root_path, matched, excluder)),
        missing=tuple(missing),
        violations=tuple(violations),
        failed=failed,
    )


def _merge_matched(
    top_nodes: tuple[Node, ...],
    root_path: Path,
    excluder: Callable[[Path], bool] | None,
) -> dict[Path, tuple[Node, ...]]:
    """Union each top node's `locate_map`, by path (spec order kept).

    Takes the pre-built `excluder` predicate so every top node reuses one
    excluder instead of rebuilding it per `locate_map` call.
    """
    merged: dict[Path, tuple[Node, ...]] = {}
    for node in top_nodes:
        for path, nodes in _locate_map(node, root_path, excluder).items():
            merged[path] = merged.get(path, ()) + nodes
    return merged


def _check_group(
    group: Group, present: set[Node]
) -> tuple[Violation | None, bool, tuple[Node, ...]]:
    """Inspect one constraint; return `(violation, is_missing, demoted)`.

    `demoted` is non-empty only when a `priority` `Exclusive` resolves a
    multi-side conflict: it is every node beneath the losing (lower-priority)
    present sides, which the caller drops from `matched` (so they surface as
    `unexpected`) and skips in the spec walk.
    """
    if isinstance(group, Exclusive):
        present_sides = [
            side for side in group.alternatives if _present_leaves(side, present)
        ]
        if len(present_sides) > 1:
            if group.on_conflict == "priority":
                demoted = tuple(
                    descendant
                    for side in present_sides[1:]
                    for node in side
                    for descendant in _walk_nodes(node)
                )
                return None, False, demoted
            leaves = _present_leaves(group.entries, present)
            return Violation("exclusive", group, leaves), False, ()
        return None, group.required and not present_sides, ()

    together = cast("Together", group)
    present_members = [
        member for member in together.members if _present_leaves((member,), present)
    ]
    if 0 < len(present_members) < len(together.members):
        leaves = _present_leaves(together.entries, present)
        return Violation("together", together, leaves), False, ()
    return None, together.required and not present_members, ()


def _unexpected(
    root_path: Path,
    matched: dict[Path, tuple[Node, ...]],
    excluder: Callable[[Path], bool] | None,
) -> list[Path]:
    """List paths under `root_path` matching no node (subtrees included).

    A path is unexpected unless it is matched or an ancestor of a match; an
    unexpected directory is reported once and not descended. An excluded
    path is neither reported nor descended (it was dropped on purpose).
    """
    allowed: set[Path] = set(matched)
    for path in matched:
        allowed.update(path.parents)

    def keep(candidate: Path) -> bool:
        return candidate in allowed or (excluder is not None and excluder(candidate))

    result: list[Path] = []
    for dirpath, dirnames, filenames in root_path.walk(top_down=True):
        for name in filenames:
            candidate = dirpath / name
            if not keep(candidate):
                result.append(candidate)
        kept: list[str] = []
        for name in dirnames:
            candidate = dirpath / name
            if candidate in allowed:
                kept.append(name)  # descend (matched dir or ancestor of a match)
            elif not keep(candidate):  # not allowed, not excluded -> report and prune
                result.append(candidate)
        dirnames[:] = kept
    return result


def _walk_nodes(node: Node) -> Iterator[Node]:
    """Yield `node` and every node beneath it (descending into groups)."""
    yield node
    if isinstance(node, Directory):
        for child in node.children:
            yield from _walk_nodes(child)
    elif isinstance(node, Exclusive):
        for alternative in node.alternatives:
            for member in alternative:
                yield from _walk_nodes(member)
    elif isinstance(node, Together):
        for member in node.members:
            yield from _walk_nodes(member)


def _present_leaves(nodes: Iterable[Node], present: set[Node]) -> tuple[Entry, ...]:
    """The leaf entries of `nodes` that are present on disk."""
    return tuple(entry for entry in flatten_entries(nodes) if entry in present)


# ========================== #
#          Conforms          #
# ========================== #


def conforms(
    spec: Node,
    *,
    checks: ContentChecks | None = None,
    on_missing: Literal["error", "skip"] = "error",
) -> Callable[[StrPath], bool]:
    """Build a `search` predicate that accepts a path realizing `spec`'s top.

    The returned `Callable[[Path], bool]` accepts `path` when it realizes
    the top of `spec`: a `File` whose name matches (and is a file) and whose
    `condition` holds, or a `Directory` whose name matches, whose subtree
    conforms, and whose `condition` holds; a top `Group` is realized by any
    one of its alternatives / members. The path is always tested as the top
    of `spec`, never against one of its inner nodes -- e.g.
    `conforms(Directory("dataset", [...]))` accepts a conforming `dataset/`
    directory, not the files inside it. `checks` / `on_missing` supply and
    resolve `Content` conditions as in `validate`.

    For an `Entry` top this is exactly `validate(spec, path, at_root=True).ok`;
    a `Group` top conforms when any of its leaf entries does.

    (Checking whether a concrete path or a sub-spec is *contained* anywhere
    within a spec is a separate, future capability.)
    """
    ctx = CheckContext(checks or {}, on_missing)
    tops = spec.entries if isinstance(spec, Group) else (spec,)

    def check(path: StrPath) -> bool:
        candidate = Path(path)
        return any(_validate_at_root(top, candidate, None, ctx).ok for top in tops)

    return check

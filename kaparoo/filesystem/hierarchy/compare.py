from __future__ import annotations

__all__ = (
    "ValidationReport",
    "Violation",
    "conformer",
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
    max_depth_of,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

    from kaparoo.filesystem.exclude import ExcludeRule
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
    exclude: ExcludeRule | Iterable[ExcludeRule] | None = None,
    at_root: bool = False,
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
            `at_root`.
        unique: Suppress duplicate `(path, node)` pairs (a reused subtree
            otherwise repeats once per occurrence); iteration stays lazy.
        exclude: Path(s) to drop -- a `StrPath` (absolute under `root` or
            root-relative), a `Filter` (on the root-relative POSIX path), a
            callable on the candidate's real `Path`, or an iterable of these
            (OR-combined). A dropped directory is pruned whole.
        at_root: Treat `root` *itself* as the realized top rather than its
            container; the top must be an `Entry`, realized only when `root`'s
            leaf name and kind match it.

    Yields:
        `(path, node)` in depth-first order, a path's overlapping nodes in
        spec order.

    Raises:
        TypeError: If `at_root` and `tree`'s top is a `Group`.
    """
    root = Path(root)
    excluder = build_excluder(exclude, root)
    locate_fn = _locate_at_root if at_root else _locate_under
    pairs = locate_fn(tree, root, excluder)
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

    Separate from `locate_map` so `validate` builds the excluder once and
    reuses it across every top node, instead of rebuilding it per call.

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


def _locate_at_root(
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
        msg = "at_root requires an Entry top node, not a Group"
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
            if (
                entry.accepts_depth(depth)
                and entry.name.matches(candidate.name)
                and entry.accepts_kind(candidate)
            ):
                yield (candidate, entry)

                if isinstance(entry, Directory):
                    yield from _locate_under(entry.children, candidate, excluder)


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
    exclude: ExcludeRule | Iterable[ExcludeRule] | None = None,
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
    root = Path(root)
    if at_root:
        return _validate_at_root(tree, root, exclude, ctx)

    return _build_report((tree,), root, exclude, ctx)


def _validate_at_root(
    top: Node,
    root: Path,
    exclude: ExcludeRule | Iterable[ExcludeRule] | None,
    ctx: CheckContext,
) -> ValidationReport:
    """Validate `root` as the realized top entry, not as a container.

    The `at_root` form of `_build_report`. When `root` does not realize
    `top` (leaf name / kind mismatch) the top is reported `missing` and the
    subtree is not descended; otherwise the directory's children are validated
    beneath `root` and the top's own `condition` is checked on it.

    Raises:
        TypeError: If `top` is a `Group` (it has no single name to anchor).
    """
    if isinstance(top, Group):
        msg = "at_root requires an Entry top node, not a Group"
        raise TypeError(msg)

    entry = cast("Entry", top)
    if not (entry.name.matches(root.name) and entry.accepts_kind(root)):
        return ValidationReport({}, (), (entry,), (), ())

    if isinstance(entry, File):
        failed = _failed_condition(entry, root, ctx)
        return ValidationReport({root: (entry,)}, (), (), (), failed)

    directory = cast("Directory", entry)
    report = _build_report(directory.children, root, exclude, ctx)
    return ValidationReport(
        matched={root: (entry,), **report.matched},
        unexpected=report.unexpected,
        missing=report.missing,
        violations=report.violations,
        failed=report.failed + _failed_condition(entry, root, ctx),
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
    root: Path,
    exclude: ExcludeRule | Iterable[ExcludeRule] | None = None,
    ctx: CheckContext = _NO_CHECKS,
) -> ValidationReport:
    """Validate `top_nodes` matched directly under `root`.

    The `exclude` predicate is built once here and threaded into both the
    match phase (`_merge_matched`) and the `_unexpected` sweep, rather than
    rebuilt per top node.
    """
    excluder = build_excluder(exclude, root)
    matched = _merge_matched(top_nodes, root, excluder)
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
        unexpected=tuple(_unexpected(root, matched, excluder)),
        missing=tuple(missing),
        violations=tuple(violations),
        failed=failed,
    )


def _merge_matched(
    top_nodes: tuple[Node, ...],
    root: Path,
    excluder: Callable[[Path], bool] | None,
) -> dict[Path, tuple[Node, ...]]:
    """Union each top node's `locate_map`, by path (spec order kept).

    Takes the pre-built `excluder` predicate so every top node reuses one
    excluder instead of rebuilding it per `locate_map` call.
    """
    merged: dict[Path, tuple[Node, ...]] = {}
    for node in top_nodes:
        for path, nodes in _locate_map(node, root, excluder).items():
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
    root: Path,
    matched: dict[Path, tuple[Node, ...]],
    excluder: Callable[[Path], bool] | None,
) -> list[Path]:
    """List paths under `root` matching no node (subtrees included).

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
    for dirpath, dirnames, filenames in root.walk(top_down=True):
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


def conformer(
    spec: Node,
    *,
    checks: ContentChecks | None = None,
    on_missing: Literal["error", "skip"] = "error",
) -> Callable[[StrPath], bool]:
    """Build a `search` predicate accepting paths that realize `spec`'s top.

    A path realizes the top when its name and kind match and its `condition`
    holds; a `Directory`'s subtree must also conform (via `validate`), and a
    `Group` top is realized by any one of its members. The path is tested only
    as the *top* of `spec`, never an inner node -- so
    `conformer(Directory("dataset", [...]))` accepts a conforming `dataset/`,
    not its contents. For an `Entry` top this is exactly
    `validate(spec, path, at_root=True).ok`. `checks` / `on_missing` supply
    `Content` conditions as in `validate`.

    Because the predicate enforces the top's kind, pair it with the matching
    search -- a `File` top with `search_files`, a `Directory` top with
    `search_dirs`; a kind mismatch matches nothing rather than raising.

    Args:
        spec: The spec whose top node the predicate tests.
        checks: `Content` hooks by name, supplied as in `validate`.
        on_missing: How a missing `Content` name resolves (`"error"` /
            `"skip"`), as in `validate`.

    Returns:
        A predicate that is `True` for a path realizing `spec`'s top.
    """
    ctx = CheckContext(checks or {}, on_missing)
    tops = flatten_entries(spec)

    def check(path: StrPath) -> bool:
        root = Path(path)
        return any(_validate_at_root(top, root, None, ctx).ok for top in tops)

    return check

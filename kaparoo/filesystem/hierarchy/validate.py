from __future__ import annotations

__all__ = ("ValidationReport", "Violation", "conforms", "validate")

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from kaparoo.filesystem.hierarchy.conditions import CheckContext
from kaparoo.filesystem.hierarchy.entry import Directory, Entry, File
from kaparoo.filesystem.hierarchy.group import (
    Exclusive,
    Group,
    Together,
    flatten_entries,
)
from kaparoo.filesystem.hierarchy.locate import build_excluder, locate_map

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.hierarchy.locate import Excluder
    from kaparoo.filesystem.types import StrPath

    type ContentChecks = Mapping[str, Callable[[Path], bool]]


_NO_CHECKS = CheckContext()


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
            top must be an `Entry` (a `Group` raises `ValueError`); when
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
    name_ok = entry.name.matches(root_path.name)
    if isinstance(entry, File):
        if not (name_ok and root_path.is_file()):
            return ValidationReport({}, (), (entry,), (), ())
        failed = _failed_condition(entry, root_path, ctx)
        return ValidationReport({root_path: (entry,)}, (), (), (), failed)

    directory = cast("Directory", entry)
    if not (name_ok and root_path.is_dir()):
        return ValidationReport({}, (), (entry,), (), ())

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
    conforms (via `validate`), and whose `condition` holds; a top `Group` is
    realized by any one of its alternatives / members. The path is always
    tested as the top of `spec`, never against one of its inner nodes -- e.g.
    `conforms(Directory("dataset", [...]))` accepts a conforming `dataset/`
    directory, not the files inside it. `checks` / `on_missing` supply and
    resolve `Content` conditions as in `validate`.

    (Checking whether a concrete path or a sub-spec is *contained* anywhere
    within a spec is a separate, future capability.)
    """
    ctx = CheckContext(checks or {}, on_missing)

    def check(path: StrPath) -> bool:
        return _top_conforms(spec, Path(path), ctx)

    return check


def _top_conforms(node: Node, path: Path, ctx: CheckContext) -> bool:
    """Whether `path` realizes `node` as the top of a spec."""
    if isinstance(node, Group):
        return any(_node_conforms(entry, path, ctx) for entry in node.entries)
    return _node_conforms(cast("Entry", node), path, ctx)


def _node_conforms(entry: Entry, path: Path, ctx: CheckContext) -> bool:
    """Whether `path` realizes `entry` (a file / conforming dir + condition)."""
    if isinstance(entry, File):
        structural = path.is_file() and entry.name.matches(path.name)
    else:
        directory = cast("Directory", entry)
        structural = (
            path.is_dir()
            and directory.name.matches(path.name)
            and _build_report(directory.children, path, ctx=ctx).ok
        )
    return structural and (entry.condition is None or entry.condition.check(path, ctx))


def _build_report(
    top_nodes: tuple[Node, ...],
    root_path: Path,
    exclude: Excluder | Iterable[Excluder] | None = None,
    ctx: CheckContext = _NO_CHECKS,
) -> ValidationReport:
    """Validate `top_nodes` matched directly under `root_path`."""
    matched = _merge_matched(top_nodes, root_path, exclude)
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

    excluded = build_excluder(exclude, root_path)
    return ValidationReport(
        matched=matched,
        unexpected=tuple(_unexpected(root_path, matched, excluded)),
        missing=tuple(missing),
        violations=tuple(violations),
        failed=failed,
    )


def _merge_matched(
    top_nodes: tuple[Node, ...],
    root_path: Path,
    exclude: Excluder | Iterable[Excluder] | None,
) -> dict[Path, tuple[Node, ...]]:
    """Union the `locate_map` of each top node, by path (spec order kept)."""
    merged: dict[Path, tuple[Node, ...]] = {}
    for node in top_nodes:
        for path, nodes in locate_map(node, root_path, exclude=exclude).items():
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
    excluded: Callable[[Path], bool] | None,
) -> list[Path]:
    """List paths under `root_path` matching no node (subtrees included).

    A path is unexpected unless it is matched or an ancestor of a match; an
    unexpected directory is reported once and not descended. An `excluded`
    path is neither reported nor descended (it was dropped on purpose).
    """
    allowed: set[Path] = set(matched)
    for path in matched:
        allowed.update(path.parents)

    def keep(candidate: Path) -> bool:
        return candidate in allowed or (excluded is not None and excluded(candidate))

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

"""Check a real tree against a hierarchy spec (`validate`, `conformer`)."""

from __future__ import annotations

__all__ = ("ValidationReport", "Violation", "conformer", "validate")

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from kaparoo.filesystem.exclude import build_excluder
from kaparoo.filesystem.hierarchy.base import Node
from kaparoo.filesystem.hierarchy.conditions import HookResolver
from kaparoo.filesystem.hierarchy.entry import Directory, Entry
from kaparoo.filesystem.hierarchy.group import (
    Exclusive,
    Group,
    Together,
    flatten_entries,
    max_depth_of,
)
from kaparoo.filesystem.hierarchy.traverse._utils import (
    _entry_accepts,
    _unique,
    _walk_depths,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

    from kaparoo.filesystem.exclude import ExcludeRule
    from kaparoo.filesystem.types import StrPath

    type ContentHooks = Mapping[str, Callable[[Path], bool]]


_NO_HOOKS = HookResolver()


@dataclass(frozen=True)
class Violation:
    """A constraint that a matched tree breaks.

    Attributes:
        node: The offending `Exclusive` / `Together`.
        present: The leaf entries found present -- for `exclusive`, those
            across the multiple coexisting sides; for `together`, the members
            present while others are absent.
        kind: The offending group's type (`"exclusive"` / `"together"`),
            derived from `node` so the two cannot disagree.
    """

    node: Group
    present: tuple[Entry, ...]
    kind: Literal["exclusive", "together"] = field(init=False)

    def __post_init__(self) -> None:
        kind = "exclusive" if isinstance(self.node, Exclusive) else "together"
        object.__setattr__(self, "kind", kind)


@dataclass(frozen=True)
class ValidationReport:
    """The outcome of checking a real directory against a spec tree.

    The report's truthiness is `ok`.

    Attributes:
        matched: Each on-disk path mapped to the node(s) it matched (exactly
            `locate_map`).
        unexpected: Paths matching no node (an unspecified directory's
            contents included).
        missing: `required` entries / groups left unsatisfied.
        violations: Broken `Exclusive` / `Together` constraints.
        failed: `(path, node)` pairs where the matched path broke the node's
            attribute `condition`.
    """

    matched: dict[Path, tuple[Node, ...]]
    unexpected: tuple[Path, ...]
    missing: tuple[Node, ...]
    violations: tuple[Violation, ...]
    failed: tuple[tuple[Path, Node], ...]

    @property
    def ok(self) -> bool:
        """Whether nothing is wrong (all four problem lists empty)."""
        return not (self.unexpected or self.missing or self.violations or self.failed)

    def __bool__(self) -> bool:
        return self.ok

    def __add__(self, other: object) -> ValidationReport:
        """Combine two reports from independent validations into one.

        Problem lists concatenate and `matched` merges -- a path matched in
        both keeps the union of its nodes -- so the result is `ok` only when
        both operands are. Intended for *disjoint* roots: the cross-report
        shape of `unexpected` (ancestor allowance, descendant collapse) is not
        recomputed, so overlapping trees may double-report.
        """
        if not isinstance(other, ValidationReport):
            return NotImplemented

        matched = dict(self.matched)
        for path, nodes in other.matched.items():
            matched[path] = matched.get(path, ()) + nodes

        return ValidationReport(
            matched=matched,
            unexpected=self.unexpected + other.unexpected,
            missing=self.missing + other.missing,
            violations=self.violations + other.violations,
            failed=self.failed + other.failed,
        )


def validate(
    tree: Node,
    root: StrPath,
    *,
    exclude: ExcludeRule | Iterable[ExcludeRule] | None = None,
    hooks: ContentHooks | None = None,
    on_missing: Literal["error", "skip"] = "error",
    root_as_top: bool = False,
) -> ValidationReport:
    """Check the directory at `root` against the spec `tree`.

    By default `root` is the container (as in `locate`). A path is
    `unexpected` when it is neither matched nor an ancestor of a match, so an
    unspecified directory's contents count too. A `required` entry is
    satisfied as soon as its name matches one present path -- for an
    enumerable name (`OneOf` / `Template`), *at least one* listed name must
    exist, not all. Each matched path is also checked against its entry's
    `condition`, with failures collected in `report.failed`.

    Args:
        tree: The spec to check the directory against.
        root: The directory checked; the realized top itself when `root_as_top`.
        exclude: Path(s) to drop, as in `locate` (dropped paths are not
            reported `unexpected`).
        hooks: Callables for `Content` conditions, keyed by name.
        on_missing: What to do when a `Content` name is absent -- `"error"`
            raises, `"skip"` treats it as satisfied.
        root_as_top: Treat `root` *itself* as the realized top rather than its
            container; the top must be an `Entry`, and a leaf name / kind
            mismatch reports the top as `missing` without descending.

    Returns:
        A `ValidationReport` whose `ok` is `True` when nothing is wrong.

    Raises:
        TypeError: If `root_as_top` and `tree`'s top is a `Group`.
    """
    root = Path(root)
    excluder = build_excluder(exclude, root)
    resolver = HookResolver(hooks or {}, on_missing)

    worker = _validate_as_top if root_as_top else _validate_under
    return worker(tree, root, excluder, resolver)


def _validate_as_top(
    top: Node,
    root: Path,
    excluder: Callable[[Path], bool] | None,
    resolver: HookResolver,
) -> ValidationReport:
    """Validate `root` as the realized top entry, not as a container.

    The `root_as_top` form of `_validate_under`: a `Directory`'s children are
    validated beneath `root` and the top's own `condition` is checked on it.

    Args:
        top: The spec's top node; must be an `Entry`.
        root: The path validated as the realized `top`.
        excluder: A pre-built drop predicate, or `None` to exclude nothing.
        resolver: The `Content` hook resolver (`hooks` / `on_missing`).

    Returns:
        A `ValidationReport`; when `root` does not realize `top` (leaf name /
        kind mismatch) the top is reported `missing` and not descended.

    Raises:
        TypeError: If `top` is a `Group` (it has no single name to anchor).
    """
    if isinstance(top, Group):
        msg = "root_as_top requires an Entry top node, not a Group"
        raise TypeError(msg)

    entry = cast("Entry", top)
    if not entry.matches(root):
        return ValidationReport({}, (), (entry,), (), ())

    failed: tuple[tuple[Path, Node], ...] = ()
    if not entry.accepts_condition(root, resolver):
        failed = ((root, entry),)

    report = ValidationReport({root: (entry,)}, (), (), (), failed)
    if isinstance(entry, Directory):
        report += _validate_under(entry.children, root, excluder, resolver)

    return report


def _validate_under(
    tops: Node | tuple[Node, ...],
    root: Path,
    excluder: Callable[[Path], bool] | None,
    resolver: HookResolver = _NO_HOOKS,
) -> ValidationReport:
    """Validate `tops` as entries realized directly under `root`.

    The `root_as_top`-less core of `validate`, also reused by `_validate_as_top`
    for a directory's children.

    Args:
        tops: The sibling nodes expected directly under `root`.
        root: The directory validated.
        excluder: A pre-built drop predicate, or `None` to exclude nothing.
        resolver: The `Content` hook resolver.

    Returns:
        The combined report for `tops` under `root`.
    """
    if isinstance(tops, Node):
        tops = (tops,)

    matched, seen = _scan_under(tops, root, excluder)
    present: set[Node] = {node for nodes in matched.values() for node in nodes}

    missing: list[Node] = []
    violations: list[Violation] = []
    demoted: set[int] = set()

    for top in tops:
        for node in _walk_nodes(top):
            if id(node) in demoted:
                continue  # under a priority Exclusive's losing side

            if isinstance(node, Entry):
                if node.required and node not in present:
                    missing.append(node)
                continue

            group = cast("Group", node)
            violation, group_missing, group_demoted = _check_group(group, present)

            if violation is not None:
                violations.append(violation)

            if group_missing:
                missing.append(group)

            demoted.update(id(n) for n in group_demoted)

    pruned: dict[Path, tuple[Node, ...]] = {}
    failed: list[tuple[Path, Node]] = []

    def list_failed(path: Path, nodes: tuple[Node, ...]) -> Iterator[tuple[Path, Node]]:
        for node in nodes:
            if isinstance(node, Entry) and not node.accepts_condition(path, resolver):
                yield (path, node)

    for path, nodes in matched.items():
        if demoted:
            nodes = tuple(node for node in nodes if id(node) not in demoted)

        if not nodes:
            continue

        pruned[path] = nodes
        failed.extend(list_failed(path, nodes))

    return ValidationReport(
        matched=pruned,
        unexpected=_build_unexpected(seen, pruned),
        missing=tuple(missing),
        violations=tuple(violations),
        failed=tuple(failed),
    )


def _scan_under(
    tops: tuple[Node, ...],
    root: Path,
    excluder: Callable[[Path], bool] | None,
) -> tuple[dict[Path, tuple[Node, ...]], set[Path]]:
    """Locate `tops` under `root`, returning the matches and every path seen.

    `matched` maps each on-disk path to the distinct nodes it matches; `seen`
    is every non-excluded path visited -- the candidates for `unexpected`.

    Args:
        tops: The sibling top nodes expected under `root`.
        root: The directory walked.
        excluder: A pre-built drop predicate, or `None` to exclude nothing.

    Returns:
        `(matched, seen)` -- each matched path mapped to its distinct nodes,
        and every non-excluded path visited.
    """
    pairs: list[tuple[Path, Node]] = []
    seen: set[Path] = set()
    _scan_entries(flatten_entries(tops), root, excluder, pairs, seen)

    matched: dict[Path, list[Node]] = {}
    for path, node in _unique(pairs):
        matched.setdefault(path, []).append(node)

    return {path: tuple(nodes) for path, nodes in matched.items()}, seen


def _scan_entries(
    entries: tuple[Entry, ...],
    parent: Path,
    excluder: Callable[[Path], bool] | None,
    pairs: list[tuple[Path, Node]],
    seen: set[Path],
) -> None:
    """Match `parent`'s descendants against `entries`, recording every path seen.

    A matched `Directory` is descended even when its child spec is empty, so
    strays inside an otherwise-unconstrained matched directory still surface as
    `unexpected`.

    Args:
        entries: The leaf entries expected at or below `parent` (flattened).
        parent: The directory walked for these entries.
        excluder: A pre-built drop predicate, or `None` to exclude nothing.
        pairs: Accumulator for `(path, entry)` matches.
        seen: Accumulator for every non-excluded path visited.
    """
    max_depth = max_depth_of(entries) if entries else 1

    for candidate, depth in _walk_depths(parent, max_depth, excluder):
        seen.add(candidate)
        for entry in entries:
            if _entry_accepts(entry, candidate, depth):
                pairs.append((candidate, entry))
                if isinstance(entry, Directory):
                    child_entries = flatten_entries(entry.children)
                    _scan_entries(child_entries, candidate, excluder, pairs, seen)


def _check_group(
    group: Group, present: set[Node]
) -> tuple[Violation | None, bool, tuple[Node, ...]]:
    """Inspect one constraint against the present nodes.

    Args:
        group: The `Exclusive` / `Together` to inspect.
        present: Every node found present on disk.

    Returns:
        `(violation, is_missing, demoted)`. `demoted` is non-empty only when a
        `priority` `Exclusive` resolves a multi-side conflict: every node
        beneath the losing (lower-priority) present sides, which the caller
        drops from `matched` (so they surface as `unexpected`) and skips in
        the spec walk.
    """

    match group:
        case Together():
            present_members = [
                member for member in group.members if _present_leaves(member, present)
            ]
            num_presents = len(present_members)
            has_violation = 0 < num_presents < len(group.members)

        case Exclusive():
            present_sides = [
                side for side in group.alternatives if _present_leaves(side, present)
            ]
            num_presents = len(present_sides)
            has_violation = num_presents > 1

            if has_violation and group.on_conflict == "priority":
                # Demote every node beneath the lower-priority present sides.
                demoted: list[Node] = []
                for side in present_sides[1:]:
                    for node in side:
                        demoted.extend(_walk_nodes(node))
                return None, False, tuple(demoted)

    if has_violation:
        leaves = _present_leaves(group.entries, present)
        return Violation(group, leaves), False, ()

    return None, group.required and num_presents == 0, ()  # default return


def _build_unexpected(
    seen: set[Path], matched: dict[Path, tuple[Node, ...]]
) -> tuple[Path, ...]:
    """Derive the unexpected paths from `seen` and the final `matched` map.

    A seen path is unexpected unless it is matched or an ancestor of a match;
    an unexpected directory collapses its already-seen descendants (reported
    once). Excluded paths never enter `seen`, so they are neither matched nor
    reported.

    Args:
        seen: Every non-excluded path the walk visited.
        matched: The final matched map (after demotion).

    Returns:
        The unexpected paths, ancestor before descendant.
    """

    def iter_ancestors(path: Path, allowed: set[Path]) -> Iterator[Path]:
        parent = path.parent
        while parent not in allowed:
            yield parent
            if (grandparent := parent.parent) == parent:
                break  # reached the anchor
            parent = grandparent

    allowed: set[Path] = set(matched)

    for path in matched:
        for ancestor in iter_ancestors(path, allowed):
            allowed.add(ancestor)

    result: list[Path] = []
    reported: set[Path] = set()

    for path in sorted(seen):
        if path in allowed:
            continue

        for ancestor in iter_ancestors(path, allowed):
            if ancestor in reported:
                break
        else:
            result.append(path)
            reported.add(path)

    return tuple(result)


def _walk_nodes(node: Node) -> Iterator[Node]:
    """Yield `node` and every node beneath it (descending into groups).

    Args:
        node: The subtree root to traverse.

    Yields:
        Each node in the subtree, `node` first.
    """
    yield node

    match node:
        case Directory():
            for child in node.children:
                yield from _walk_nodes(child)
        case Together():
            for member in node.members:
                yield from _walk_nodes(member)
        case Exclusive():
            for alternative in node.alternatives:
                for member in alternative:
                    yield from _walk_nodes(member)


def _present_leaves(
    nodes: Node | Iterable[Node], present: set[Node]
) -> tuple[Entry, ...]:
    """Filter `nodes`' leaf entries to those present on disk.

    Args:
        nodes: The nodes whose leaf entries are considered.
        present: Every node found present on disk.

    Returns:
        The present leaf entries of `nodes`, in flattened order.
    """
    return tuple(entry for entry in flatten_entries(nodes) if entry in present)


def conformer(
    spec: Node,
    *,
    hooks: ContentHooks | None = None,
    on_missing: Literal["error", "skip"] = "error",
) -> Callable[[StrPath], bool]:
    """Build a `search` predicate accepting paths that realize `spec`'s top.

    A path realizes the top when its name and kind match and its `condition`
    holds; a `Directory`'s subtree must also conform (via `validate`), and a
    `Group` top is realized by any one of its members. The path is tested only
    as the *top* of `spec`, never an inner node -- so
    `conformer(Directory("dataset", [...]))` accepts a conforming `dataset/`,
    not its contents. For an `Entry` top this is exactly
    `validate(spec, path, root_as_top=True).ok`. `hooks` / `on_missing` supply
    `Content` conditions as in `validate`.

    Because the predicate enforces the top's kind, pair it with the matching
    search -- a `File` top with `search_files`, a `Directory` top with
    `search_dirs`; a kind mismatch matches nothing rather than raising.

    Args:
        spec: The spec whose top node the predicate tests.
        hooks: `Content` hooks by name, supplied as in `validate`.
        on_missing: How a missing `Content` name resolves (`"error"` /
            `"skip"`), as in `validate`.

    Returns:
        A predicate that is `True` for a path realizing `spec`'s top.
    """
    tops = flatten_entries(spec)
    excluder = None  # conformer judges each candidate strictly; no exclusions
    resolver = HookResolver(hooks or {}, on_missing)

    def check(path: StrPath) -> bool:
        root = Path(path)
        return any(_validate_as_top(top, root, excluder, resolver).ok for top in tops)

    return check

# TODO

Tracked items that are not yet captured in code or tests, organized by
module. Promote an item to a CHANGELOG entry once it lands.

---

## 🧮 `kaparoo.utils.aggregate`

### `Stored` reduction (deferred — add when concrete need arises)

Non-decomposable statistics (median, quantiles) that require storing every
`(value, weight)` pair. O(n) memory — documented escape hatch from the
online monoid contract.

```python
@dataclass(frozen=True)
class Stored(Reduction[list[tuple[float, float]]]):
    reduce: Callable[[Sequence[float], Sequence[float]], float]
```

Convenience wrappers built on top: `Median()`, `Quantile(q)`.

**Blocker before shipping**: `state()` docstring claims states are immutable;
`Stored.step` would mutate a list. Resolve by relaxing the docstring or
returning a new list in `step`.

### Remove `experimental` tag

Once the reduction family is complete (after `Stored` is merged or explicitly
decided against), remove the `experimental` note from the module docstring,
class docstrings, CHANGELOG entry, and `kaparoo/utils/README.md`.

### `Aggregator.weight` per-metric tracking (deferred)

`weight` is now documented as a grand total over all `update` calls,
independent of each call's key set (so it need not match any single
metric's effective weight under heterogeneous updates). A parallel
per-metric weight dict was considered and declined: a weighted reduction
already tracks its own weight in its state (`Mean`'s `total_weight`,
`Var` / `Std`'s `weight`), and the number is murky for the unweighted
reductions that discard weight. Revisit only if a concrete need for a
uniform per-metric input weight appears.

### `Min` / `Max` / `Last` duplication (refactor — deferred)

The three "optional float" reductions repeat the same shape: a `float |
None` state, `result` projecting `None -> nan`, and a `merge` with `None`
as the identity (`if a is None: return b` / `if b is None: return a`). A
small `_OptionalFold` mixin (state `float | None`, the shared `merge` /
`result`, an abstract `_combine`) would remove ~20 lines. Deferred:
`aggregate` is experimental, so hold the extra hierarchy layer until the
API stabilizes -- and add a one-line comment on `Min` / `Max` explaining
why they are *not* `Fold(min, inf)` / `Fold(max, -inf)` (their empty case
is `nan`, not the fold's `initial`), so a future maintainer does not
"simplify" them away. (The positive-weight contract from the review is
already documented on `Reduction`.)

---

## 🌳 `kaparoo.filesystem.hierarchy`

### Scaffolder (the remaining spec operation)

`match` / `match_map` (`match.py`), `validate`, and `conforms`
(`validate.py`) have landed: `match` maps each on-disk path to its spec
node(s) honoring `depth` and descending through `Group`s; `validate`
returns a conformance report (`matched` / `unexpected` / `missing` /
`violations`); `conforms(spec)` builds a `search` predicate accepting a
path that realizes *any* entry in the spec (file by name, directory by name
+ conforming subtree). Settled policies: `required`-enumerable is **"at
least one present"**; `unexpected` is **"not matched and not an ancestor of
a match"**; `conforms` matches **any node** in the spec, not just the top.
The operation still to write — a free function, nodes as pure value
objects, reusing `search`'s traversal and `stringify_path` where helpful:

- `scaffold(tree, root)` — write op: create the tree from `Expandable`
  names (and `required`).

`match` does not replace `search`: `search` *discovers* paths matching
stateless filters; `match` *checks / maps* a real tree against a known
structural spec (depth, constraints, presence). They share `kaparoo.filters`
and may share traversal, but answer different questions.

### `match` path exclusion (`exclude=`) — follow-up

`match` / `match_map` / `validate` take `exclude=` (a `StrPath` or
`Callable[[Path], bool]`, or an iterable of them, over the **root-relative**
path; a dropped directory is pruned, and excluded paths are not reported
`unexpected`). Remaining:

- **`Node` / sub-spec excluder** stays deferred: it would need an extra
  `match` pass and terminal-node rules, and its main draw (declarative +
  serializable) barely applies since `exclude` lives on the call, not the
  serialized representation; the pattern case is covered by a callable.
  Revisit on concrete need.

### Attribute conditions on `File` / `Directory` — landed; extensions deferred

The `conditions` DSL has landed (`conditions.py`): `File` / `Directory`
take a `condition`, `validate` checks it and reports `failed`, content
checks go through the `Content` named hook + `validate(checks=...)`. New
condition *kinds* can be added non-breakingly when a concrete need appears:

- **`mtime` / age** — serializable as an absolute timestamp but
  time/environment-dependent, so a poor fit for a value-compared spec;
  cover one-offs via a `Content` callable for now.
- **`Symlink(bool)`**, **`Checksum(algo, hex)`** (a serializable content
  check), **`ChildCount(kind="file" | "dir")`** — all niche; defer.
- **permissions / mode** — Windows ignores mode, so non-deterministic;
  avoid.

### `required` default — decided: keep `False`

The presence flag stays opt-in (`required=False`). Flipping it to
"listed = required" is rejected: it breaks pattern entries whose natural
meaning is zero-or-more (`File(Glob("*.png"))`). The opt-in policy is now
documented (Entry docstring / README); a `validate(require_all=...)` mode
remains a non-breaking future option if a concrete need appears.

### Path-name sugar — decided: no

Node-name sugar (`File("x")`, `Directory(["a", "b"])`) names a *single*
path component; a separator (`/` or `\`) stays a `ValueError`. Expanding a
separator-containing name into nested nodes (`Directory("a/b/c", children)`
-> nested directories) is **not** added to the `str` sugar: it would
overload the string (sometimes one `Literal`, sometimes a whole subtree)
and interact awkwardly with `depth` (which level applies?). If a concrete
need arises, add it as a *separate, explicit* API (e.g. a `nested(...)`
factory whose meaning is unambiguous), never via the `str` sugar.

### Spec containment / inclusion (future)

`conforms(spec)` tests a path as `spec`'s *top* node only. The broader
question -- is a concrete path, or another (sub-)spec, *contained* anywhere
within a spec? -- is deliberately left out of `conforms` and is a separate
future capability (e.g. `contains(spec, path)` / `contains(spec, subspec)`).
This is what the earlier "match any entry in the spec" idea becomes once it
is given its own, explicit operation rather than overloading `conforms`.

### Operation throughput (perf — deferred)

From the codebase-wide perf review; the higher-value wins already landed
(the single-walk `_match_children` rewrite, filter set-membership
precompute, search `stringify_path` guard). Remaining:

- **`validate` walks the disk twice** — once via `match_map` (spec-driven)
  and once in `_unexpected` (disk-driven). It is a constant 2× factor, not
  an algorithmic blow-up; collapsing it needs a disk-driven pass that
  classifies matched vs unexpected in a single walk. Defer until profiling
  shows it matters. **Note on equivalence**: done correctly the results are
  identical *as sets* (`ok`, `missing`, `violations` unchanged), but the
  order of `report.matched` keys would shift from spec-traversal to
  disk-traversal order; and the inversion (carrying active spec nodes +
  ancestor-relative depth down the disk walk) is subtle enough to risk an
  accidental behavioral change, so guard it with the existing 100% tests
  (made order-insensitive) before adopting.
- **`conforms(spec)` re-validates per candidate** — used as a `search`
  predicate over many directories, it re-walks each candidate's subtree
  (O(paths × subtree)). Inherent to the per-path "is this a conforming
  instance?" semantics; documented cost, not easily removable.

---

## 🗂️ `kaparoo.filesystem`

### Cleanups from the workspace review (refactor — deferred)

Behavior-preserving tidy-ups; low urgency, deferred to avoid churn:

- **`Search._filter_part` / `_filter_name` are byte-identical** and the
  None-guard inside them is already re-checked at the call sites
  (`Search.run` guards `part_filter is None`; `_filter_names` guards before
  calling `_filter_name`), so those `if filter is None` branches are dead on
  the real path. Collapse to one `_matches(name, filter)` helper, dropping
  ~10 lines and the `# noqa: A002` shadow-builtin suppressions.
- **`StagedFile.commit` / `StagedDirectory.commit` repeat scaffolding** --
  the `if self._committed: return` guard, the `_finalizer.alive` check, and
  the inherit-mode (`_default_*_mode()` + `contextlib.suppress(OSError)`)
  block. Lift a `StagedTarget._begin_commit()` guard and a
  `_resolve_commit_mode(default)` helper so each `commit` keeps only its
  genuinely different middle (atomic file move vs directory swap). Also
  reorder so the umask-reading default mode is computed only in the branch
  that uses it (skip it on the `overwrite=True` + existing-dest path).
- **`_ensure_directory_target` still does 2–3 stats per path in
  `make_dirs`** (the `make_dir` redundant-stat was already addressed). Apply
  the same single-`exists`-then-`is_dir` shape, threading the result through
  the validate→create loop -- but note caching `is_dir` across that gap can
  change behavior for overlapping / nested path lists (see the `make_dir`
  commit), so only the per-path stat collapse is safe, not cross-pass reuse.

---

## 🧱 `kaparoo.data.sequences`

### Index-resolution consistency (doc — deferred)

`SlicedSequence` resolves indices by **tuple semantics** (negative wraps
against the slice length, out-of-range raises a bare `IndexError`), while
`ConcatSequence` / `WindowedSequence` / `ZippedSequence` use `_resolve_index`
(`IndexError("index {i} out of range for length {n}")`) and
`TransformedSequence` forwards the raw index to its source. The behaviors
agree in spirit but the *error messages* differ. It is defensible (and
partly documented on `SlicedSequence`), but note in `_resolve_index`'s
docstring that `SlicedSequence` intentionally opts out, so the divergence is
discoverable.

### Batch-delegating `get_items` on `ConcatSequence` (perf)

`SlicedSequence` / `TransformedSequence` / `WindowedSequence` now delegate
batched access to their source's `get_items` (and `ZippedSequence` already
did). `ConcatSequence` still loops `get_item`, because batching it means
resolving each index, grouping the locals by source, issuing one
`source.get_items(...)` per source, and scattering the results back to the
caller's order. Left for when that complexity is justified by a source
that implements batch reads (the default `get_items` is a scalar loop, so
there is no gain until then).

---

*Last updated: 2026-06-07*

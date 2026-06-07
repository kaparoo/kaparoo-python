# TODO

Outstanding work not yet in code or tests, by module. Promote an item to a
CHANGELOG entry once it lands.

---

## 🧮 `kaparoo.utils.aggregate`

### `Stored` reduction (when a concrete need arises)

Non-decomposable statistics (median, quantiles) that must store every
`(value, weight)` pair -- O(n) memory, a documented escape hatch from the
online monoid contract:

```python
@dataclass(frozen=True)
class Stored(Reduction[list[tuple[float, float]]]):
    reduce: Callable[[Sequence[float], Sequence[float]], float]
```

with `Median()` / `Quantile(q)` on top. **Blocker**: `state()` documents
states as immutable, but `Stored.step` mutates a list -- relax the docstring
or return a new list in `step`.

### Remove the `experimental` tag

Once the reduction family is settled (after `Stored` lands or is dropped),
remove the `experimental` note from the module / class docstrings, the
CHANGELOG entry, and `kaparoo/utils/README.md`.

### `Min` / `Max` / `Last` duplication (refactor)

The three "optional float" reductions repeat the same `float | None` state,
`None -> nan` `result`, and `None`-identity `merge`. An `OptionalFold` mixin
(shared `merge` / `result`, abstract `_combine`) would cut ~20 lines. Hold
the extra layer until `aggregate` stabilizes; when done, comment why `Min` /
`Max` are not `Fold(min, inf)` / `Fold(max, -inf)` (empty is `nan`, not the
fold's `initial`).

---

## 🌳 `kaparoo.filesystem.hierarchy`

### `scaffold` (the remaining spec operation)

`scaffold(tree, root)` -- the write op that creates the tree on disk from
`Expandable` names (and `required`). A free function alongside `match` /
`validate` / `conforms`. The lazy plan-vs-apply / early-stop design was
discussed but parked for a closer look before building.

### Deferred extensions

- **`exclude=` `Node` / sub-spec excluder** -- a sub-spec whose terminal
  nodes' matches are dropped. Needs an extra `match` pass + terminal rules,
  and the declarative/serializable draw barely applies (exclude lives on the
  call, not the representation; patterns are covered by a callable).
- **More condition kinds** -- `mtime` / age (time-dependent; use a `Content`
  callable for now), `Symlink`, `Checksum(algo, hex)`, `ChildCount(kind=)`;
  mode is skipped (Windows ignores it). Each is a non-breaking new kind.
- **Spec containment** -- `conforms` tests a path as the *top* node only;
  whether a path or sub-spec is *contained* anywhere within a spec is a
  separate future op (`contains(spec, path)` / `contains(spec, subspec)`).

### Operation throughput (perf)

- **`validate` walks the disk twice** (`match_map` spec-driven + `_unexpected`
  disk-driven) -- a constant 2x factor. Collapsing it needs a disk-driven
  single pass; done right the results match *as sets* but `report.matched`
  key order shifts, and the inversion is subtle, so guard it with the
  existing tests (made order-insensitive). Defer until profiled.
- **`conforms` re-validates per candidate** (O(paths x subtree)) -- inherent
  to the per-path semantics; documented cost.

---

## 🗂️ `kaparoo.filesystem`

### Review cleanups (refactor -- behavior-preserving)

- **`Search._filter_part` / `_filter_name` are byte-identical** and their
  None-guard is already re-checked at every call site (dead branches).
  Collapse to one `_matches(name, filter)`; drops ~10 lines and the
  `# noqa: A002` suppressions.
- **`StagedFile.commit` / `StagedDirectory.commit` repeat scaffolding** (the
  committed guard, the `_finalizer.alive` check, the inherit-mode block).
  Lift a `StagedTarget._begin_commit()` + `_resolve_commit_mode(default)`;
  also compute the umask-reading default only in the branch that uses it.
- **`_ensure_directory_target` does 2-3 stats per path in `make_dirs`** --
  apply the single-`exists`-then-`is_dir` shape (per-path only; caching
  `is_dir` across the validate->create gap changes behavior for nested
  paths, per the `make_dir` commit).

---

## 🧱 `kaparoo.data.sequences`

### `SlicedSequence` index-resolution note (doc)

`SlicedSequence` resolves indices by tuple semantics (negative wraps, a bare
`IndexError`), unlike the `_resolve_index` users (Concat / Windowed / Zipped)
and `TransformedSequence` (forwards to its source). Behaviors agree but
messages differ -- note in `_resolve_index`'s docstring that `SlicedSequence`
intentionally opts out.

### `ConcatSequence` batch `get_items` (perf)

The other composers delegate batched access to their source; `ConcatSequence`
still loops `get_item` because batching it means grouping resolved locals by
source and scattering results back. Worth it once a source implements batch
reads (the default `get_items` is a scalar loop, so no gain until then).

---

*Last updated: 2026-06-07*

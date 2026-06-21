# TODO

Outstanding work not yet in code or tests. Promote an item to a CHANGELOG
entry once it lands.

## 🧹 Minor improvements (low priority)

Surfaced by a source review; none are bugs.

- `kaparoo.utils.aggregate.Aggregator.merge` rejects two trackers whose
  reductions are equivalent but built from separate callables (`Fold`,
  `Stored`) -- value-equality compares the lambdas. Documented for `Stored`;
  extend the note to `Fold`, or key the compatibility check on `type` for
  callable-bearing reductions.
- `Aggregator.update` adds `weight` to the grand total even for an empty
  `values={}` batch. Skip the bump, or document it.
- `kaparoo.filesystem.make_dirs` with a duplicated path and `exist_ok=False`
  leaves a partial side effect (the second `mkdir` fails after the first
  created it); the validate-first pass cannot catch duplicates. Dedup or note.
- `kaparoo.filesystem.wrap_path`'s prepend guard uses `os.path.isabs`, which
  misses Windows drive-relative paths (`C:foo`).
- `kaparoo.filters.TemplateFilter.matches` materializes the full cartesian
  product into a `frozenset` on first call -- a memory pitfall for very large
  axes (`expand()` stays lazy). Document the eager-cache cost.
- `kaparoo.filesystem.hierarchy.locate` / `validate` yield in only
  locally-sorted order (siblings sorted; sibling-subtree order follows
  `os.walk`). The *report* is sorted, so only the lazy stream order is
  non-deterministic -- document, or sort the stream.

---

## ✅ Test completeness (low priority)

Behaviors with full line coverage but no value-asserting test:

- `ChildCount(only=...)` / `TreeSize` symlink-follow semantics.
- The `stringify=True` branch of the bulk `ensure_*` / `dirs_*` helpers.
- `reserve_paths`' documented non-rollback of `make_parents` side effects.
- `Quantile` at a non-endpoint `q` (e.g. `0.9`) and `Std` merge via `Aggregator`.
- The lazy-factory contract of the `optional` helpers (factory not called on
  the present-value path).

---

*Last updated: 2026-06-22*

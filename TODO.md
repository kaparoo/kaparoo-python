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
- `kaparoo.filesystem.hierarchy.locate` / `validate` yield in only
  locally-sorted order (siblings sorted; sibling-subtree order follows
  `os.walk`). The *report* is sorted, so only the lazy stream order is
  non-deterministic -- document, or sort the stream.

---

*Last updated: 2026-06-22*

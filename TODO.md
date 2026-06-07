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

*Last updated: 2026-06-07*

# TODO

Tracked items that are not yet captured in code or tests. Promote an
item to a CHANGELOG entry once it lands.

---

## 🧮 `kaparoo.utils.aggregate` — stabilization

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

---

## 🛠 `kaparoo.filesystem.staged` — known limitations (documented)

Tracked for visibility; no action until a concrete motivation arises.

### Hardlink fallback TOCTOU (`StagedFile`, non-overwrite)

When `hardlink_to` fails (FAT/exFAT), the fallback does `exists()` then
`replace()`. A file appearing between those two calls could be clobbered.
Unavoidable without an OS-level atomic no-clobber rename primitive.
Documented in code and class docstring.

### Workdir contents not fsynced (`StagedDirectory`)

`commit` fsyncs the parent directory entry (the rename) but not the files
the caller wrote into `workdir`. Documented as caller's responsibility.

### Crash window in `overwrite=True` (`StagedDirectory`)

A crash between the two renames (`dest→.old`, `staged→dest`) leaves `.old`
as a manual recovery artifact. Fully atomic directory replace is not possible
on any mainstream OS. Documented in class docstring.

---

## 📝 Known design limitations (documentation-only resolution)

### `Aggregator.weight` semantics with heterogeneous updates

`weight` accumulates across all `update` calls regardless of which metric
keys were present. Ambiguous when updates have varying key sets. Document
explicitly or add per-metric weight tracking if a concrete case demands it.

---

*Last updated: 2026-06-04*

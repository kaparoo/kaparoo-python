# Changelog

All notable changes to this project will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `kaparoo.utils.aggregate` module **(experimental / WIP -- API may change
  before release)**: `Aggregator` for nested, pluggable metric aggregation
  (the batch → epoch → run pattern). Each metric is
  reduced by a `Reduction` -- built-ins `Mean` (weighted), `Sum`, `Min`,
  `Max`, `Last`, and `Fold` (a scalar monoid from a callable) -- with
  per-metric `overrides`. Reductions are online (constant memory); nested
  levels compose via `merge` (exact sample-weighted pooling) or
  `update(child.compute(), ...)` (different reduction per level). Custom
  reductions subclass `Reduction` / `UnweightedReduction`.
- `SegmentTimer.measure(label)`: a stopwatch-style context manager (and
  decorator) that records a segment covering only the wrapped block, so
  time spent outside any `measure` block is excluded from `records` /
  `summary`. Complements `lap`, which splits the timeline into
  contiguous segments. Pauses inside the block are excluded; a block
  that raises records nothing.

### Changed

- Renamed `LapTimer` -> `SegmentTimer`, `LapRecord` -> `SegmentRecord`,
  and the record field `lap_time` -> `duration`, reflecting that the
  timer now records named *segments* via both `lap` (split) and the new
  `measure` (block). The `lap` method keeps its name.
- `Timer.resume` / `SegmentTimer.resume` now return `None` instead of
  the pause duration in nanoseconds. The value had no consumer
  (`suspend` discarded it) and leaked a raw-nanosecond figure that broke
  the timer's `unit` abstraction. Subclasses that need the pause
  interval override the new protected `_resume` hook instead.

## [0.3.0] - 2026-05-28

### Added

- `kaparoo.data.sequences` subpackage: a `Sequence`-based foundation for
  dataset code.
  - `DataSequence[T, M]` ABC with abstract `get_item` / `get_meta` and
    default `get_items` / `get_metas` / `get_pair` / `get_pairs`.
    `__getitem__` returns the item only.
  - Composers: `SlicedSequence` (stable-length view at given indices,
    duplicates allowed and order preserved); `ConcatSequence`
    (O(log N) lookup over multiple sources via cumulative lengths +
    `bisect_right`); `WindowedSequence[T, M_in, M_out]` (abstract
    sliding window with `size` / `step` / `skip`; `get_item` is
    implemented, `get_meta` is left abstract).
  - Templates: `FileFolderSequence` (folder-rooted, one file per item;
    subclasses implement `list_files` / `load_file` / `get_meta`;
    supports the "set state BEFORE `super().__init__()`" pattern for
    parameterized subclasses); `SingleFileSequence` (thin ABC for
    "one file, many records" formats).

### Changed

- `generate_batches`: `step`, `skip`, `start`, `stop`, and `drop_last`
  are now keyword-only. Empty ranges (`start == stop`) are accepted
  and yield no batches. Docstring expanded.

### Fixed

- `register_filter` decorator now preserves the decorated subclass's
  type. Previously it widened to `type[Filter]`, so static checkers
  rejected subclass-specific constructor calls at decorated classes.
- `generate_batches` with `drop_last=False`: the final partial window
  no longer extends past `stop` when `stop < len(sequence)`.

### Removed

- `kaparoo.data.sequence` (single module) and `kaparoo.data.utils` —
  replaced by the `kaparoo.data.sequences` subpackage. The previous
  `DataSequence.by_index` / `by_indices` API was a placeholder and
  has been superseded by `get_item` / `get_items` / `get_meta` /
  `get_metas` / `get_pair` / `get_pairs`.

## [0.2.1] - 2026-05-27

### Added

- Filter serialization: `Filter.to_dict()` / `Filter.from_dict()` with
  a `"kind"`-discriminated polymorphic dispatcher. Each concrete
  filter round-trips through a JSON-compatible dict.
- `register_filter(kind)` decorator for registering custom `Filter`
  subclasses with the polymorphic dispatcher.
- `Filter.parse(value)` — normalizes either a `Filter` instance
  (passed through) or a `FilterDict` into a `Filter`.
- `FilterDict` TypedDict family at
  `kaparoo.filesystem.search.filters.types`: `FilterDict` (base,
  `kind`-only), `PatternFilterDict`, `MultiPatternFilterDict`,
  `LogicalChildrenFilterDict`, `LogicalChildFilterDict`. User-defined
  filter dicts extend these to type-check against `Filter.parse`.
- `Search.run` / `search_paths` / `search_files` / `search_dirs`
  accept a `FilterDict` for `part_filter` and `name_filter` in
  addition to a `Filter` instance.

## [0.2.0] - 2026-05-27

### Added

- `kaparoo.filesystem.search` subpackage with a composable filter system:
  - Abstract bases: `Filter`, `PatternFilter`, `MultiPatternFilter`,
    `LogicalFilter`.
  - Pattern filters: `EqualsFilter`, `StartsWithFilter`, `EndsWithFilter`,
    `ContainsFilter`, `RegexFilter`, `GlobFilter`.
  - Multi-pattern (any-of) filters: `EqualsAnyFilter`,
    `StartsWithAnyFilter`, `EndsWithAnyFilter`, `ContainsAnyFilter`.
  - Logical filters: `AndFilter`, `OrFilter`, `NotFilter`.
  - TitleCase aliases for concrete filters (`And`, `Or`, `Not`,
    `Equals`, `StartsWith`, ..., `Glob`, `EqualsAny`, ..., `ContainsAny`).
- `search_paths`, `search_files`, `search_dirs` entry points with
  `part_filter`, `name_filter`, `predicate`, `min_depth`, `max_depth`,
  `ordered`, and `stringify`.
- `kaparoo.utils.timer` module: `Timer`, `LapTimer`, `LapRecord`.
- `make_dir`, `dir_empty_unsafe`, `dirs_empty_unsafe`.
- `before` parameter on `stringify_path` / `stringify_paths` for tail
  trimming.
- `stringify` parameter on `make_dir` / `make_dirs`.
- `README.md` module overview; `CHANGELOG.md`; `TODO.md`.

### Changed

- **Minimum Python version raised to 3.14.**
- Toolchain migrated to a copier-based template with `uv` + `ty` +
  `ruff` + `pytest`.
- Adopted PEP 695 type parameters across the package.
- Renamed `prepend_path` / `prepend_paths` → `wrap_path` / `wrap_paths`;
  the renamed functions also accept a new `append` keyword argument.
- Made `root` keyword-only in `dirs_empty`.

### Deprecated

- `get_paths`, `get_files`, `get_dirs` now emit `DeprecationWarning`;
  use `search_paths` / `search_files` / `search_dirs`.

### Removed

- `kaparoo.utils.types` module (replaced by PEP 695 type parameters).
- `num_samples` parameter of `get_paths()`.

### Fixed

- Incorrect exception name in `dirs_empty` docstring.
- Typo in `DirectoryNotFoundError` docstring.

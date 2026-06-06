# Changelog

All notable changes to this project will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `kaparoo.filters` gains an enumerable filter family: `Literal`, `OneOf`,
  and `Template` implement an `Expandable` capability (`expand()`) that
  *lists* the finite set of names a filter matches, on top of the usual
  `matches`. `Literal` / `OneOf` are the case-sensitive, always-enumerable
  counterparts of `Equals` / `EqualsAny`; `Template` enumerates
  `template.format(*combo)` over the cartesian product of one or more
  value axes (`Template("shard_{:03d}", range(8))`,
  `Template("{}_{}.png", ["real", "fake"], range(3))`). They register as
  ordinary filter kinds (`"literal"` / `"one_of"` / `"template"`).
- `kaparoo.filesystem.hierarchy`: a new subpackage describing a filesystem
  tree declaratively. `File` / `Directory` nodes compose into a tree whose
  node names are `kaparoo.filters` filters — the full DSL (`Glob`,
  `Regex`, `And` / `Or` / `Not`, the enumerable `Literal` / `OneOf` /
  `Template`, ...) describes which siblings a node matches. As name sugar,
  a bare `str` becomes a `Literal` and a `list[str]` a `OneOf`, so one
  node can stand for several literally-named siblings that share a
  structure (`Directory(["train", "val"], layout)`). Nodes are immutable
  value objects (`==`, `hash`, `repr`) and take a keyword-only `depth`
  (default `1`, a direct
  child) describing how far below the parent the entry sits, past
  intermediate directories of unknown name: an `int` is an exact level,
  `None` is any depth (the tree-level `**`), and a `(min, max)` tuple is
  an inclusive range (`max=None` unbounded), exposed as `min_depth` /
  `max_depth`. Two sibling constraints can sit among a directory's
  children: `Exclusive` (the present siblings may come from at most one of
  its alternatives, each a set of independent nodes on one side of the
  exclusion; `required=True` requires at least one) and `Together` (its
  members are all-or-nothing -- all present or all absent; `required=True`
  requires all). Both take `Node`s, so constraints nest --
  `Exclusive(Together(a, b), c)` is "{a and b} or c". `File` / `Directory`
  (named, under the `Entry` base) and the constraint nodes `Exclusive` /
  `Together` (under a `Group` base that carries `required` and an
  `entries` accessor flattening to the leaf entries a constraint
  references, descending through nesting) share a common `Node` base, so a
  directory's `children` hold any `Node`. The package depends on `kaparoo.filters` but
  nothing in `kaparoo.filesystem.search`. This first cut is the
  representation plus name-level semantics; disk operations (scaffold /
  validate / match), which also consume `depth`, `Exclusive`, and
  `Together`, are not implemented yet.

### Changed

- Moved the filter DSL from `kaparoo.filesystem.search.filters` to the new
  top-level `kaparoo.filters`. The filters are a filesystem-agnostic
  string-matching DSL, now shared beyond `search`. **Breaking**: update
  imports from `kaparoo.filesystem.search.filters` to `kaparoo.filters`
  (e.g. `from kaparoo.filters import Glob, And`). Class names,
  serialization (`to_dict` / `from_dict` / `register_filter`), and
  behavior are unchanged.

## [0.7.0] - 2026-06-04

### Added

- `kaparoo.filesystem.utils.ensure_file_extension`: a pure (no filesystem)
  extension check requiring a case-insensitive `.<ext>` final suffix
  (raising `ValueError` otherwise). `ext` may be a single extension or an
  iterable of acceptable ones (e.g. `("jpg", "jpeg")`). `add=True` (mirroring
  `make` on `ensure_dir_exists`) appends the first extension when the path
  has no suffix instead of raising (`np.save`-style); a wrong suffix still
  raises. The leading dot on `ext` is optional.

### Changed

- Renamed `SegmentTimer` -> `SpanTimer` and `SegmentRecord` -> `SpanRecord`
  (module `kaparoo.utils.timer`). "Span" fits both `lap` (contiguous spans)
  and `measure` (arbitrary spans) without implying a partition, and avoids
  the "periodic timer" reading of *interval*. The `lap` / `measure` methods,
  the `duration` field, and all behavior are unchanged. **Breaking**: update
  imports from `SegmentTimer` / `SegmentRecord` to `SpanTimer` / `SpanRecord`.

## [0.6.0] - 2026-06-04

### Added

- `kaparoo.data.sequences.TransformedSequence`: a lazy view that applies a
  `transform` callable to each item of `source`. `get_meta` passes through
  `source.get_meta` by default (`M_out = M_in`); override in a subclass when
  `M_out` differs. `T_out` and `M_out` default to `T_in` / `M_in` (PEP 696).
- `kaparoo.data.sequences.ZippedSequence`: element-wise zip of two
  sequences — item `i` is `(first[i], second[i])` and metadata `i` is
  `(M1, M2)` (the "paired image + label" pattern `ConcatSequence` cannot
  express). `strict=True` (default) requires equal lengths and raises
  `ValueError` on a mismatch; `strict=False` truncates to the shorter
  length like the builtin `zip`. `get_items` / `get_metas` bulk-delegate to
  each source. For three or more, nest the pairs.

### Changed

- `WindowedSequence[T, M_in, M_out]`: `M_out` now defaults to `M_in` (PEP
  696), so the common case of `M_out == M_in` no longer requires the third
  type argument. Existing explicit three-argument usage is unaffected.
- `FileFolderSequence` is now a subclass of `FileListSequence` — the folder
  case is just a `FileListSequence` whose list is discovered under a `root`
  and stored root-relative. Its API and behavior are unchanged (paths are
  still kept relative and `get_file` re-prepends `root`), but
  `isinstance(seq, FileListSequence)` is now True for folder sequences.

## [0.5.0] - 2026-06-02

### Added

- `kaparoo.utils.aggregate` (still experimental): `Var` and `Std` reductions
  -- weighted population variance and standard deviation, accumulated online
  (Welford) and merged exactly (Chan's parallel algorithm), so they nest
  across loop levels like the other reductions.
- `kaparoo.data.sequences.FileListSequence`: a "one file per item"
  `DataSequence` over an explicit, ordered list of files. Unlike
  `FileFolderSequence` it takes the files directly (no `root` discovery),
  so they may live in unrelated directories -- or, on Windows, different
  drives -- which `FileFolderSequence` cannot represent. Subclasses
  implement only `load_file` / `get_meta`; the input order is preserved
  verbatim (duplicates kept) and files are loaded lazily.

### Fixed

- `make_dirs` now raises `NotADirectoryError` (matching `make_dir`) when a
  path exists but is not a directory, instead of the divergent
  `FileExistsError` that `mkdir` produced.
- `make_dir` / `make_dirs` validate every path *before* any directory is
  wiped or created, so a deterministically bad entry (e.g. a file in the
  list) no longer leaves earlier directories already cleaned or created.
- `make_dir(clean=True)` / `make_dirs(clean=True)` reject a symlink with
  `NotADirectoryError` rather than failing deep inside `shutil.rmtree`;
  cleaning never operates through a link.
- `reserve_path` / `reserve_paths` treat a symlink -- including a broken
  one, which `Path.exists` reports as absent -- as occupying the path.
- `StagedFile.commit` (with `overwrite=False`) no longer fails outright on a
  filesystem without hardlink support (FAT/exFAT, some network mounts): it
  falls back to an existence check plus replace instead of losing the staged
  content to a raw `OSError`.
- `StagedFile.commit` / `StagedDirectory.commit` now fsync the destination's
  parent directory after the move, so the committed result survives a crash
  on POSIX (a no-op where directories cannot be fsynced, e.g. Windows).
- `StagedDirectory.commit` with `overwrite=True` now restores the original
  directory if moving the staged one into place fails, instead of leaving
  the destination missing with the old contents stranded under a `<name>.old`
  name; the backup removal is best-effort.

## [0.4.0] - 2026-06-02

### Added

- `kaparoo.filesystem.staged.StagedFile`: a safe (atomic) file writer.
  Content is staged in a temporary file in the destination's directory and
  moved into place only on commit, so readers never see a half-written file
  and a failed write leaves any existing file untouched. Usable as a context
  manager (commit on clean exit, discard on exception) *or* explicitly like
  a file object (`write` / `seek` / `tell` / `flush`, plus `commit` /
  `abort`, `path`, `committed`, and the underlying `file`). Text by default
  (`StagedFile[str]`) with optional `encoding` / `newline`; `binary=True`
  gives a binary writer (`StagedFile[bytes]`), the type parameter tracking
  the mode. `overwrite=False` (default) fails fast on an existing destination
  and creates the file atomically; `overwrite=True` replaces it, keeping its
  permissions; `make_parents=True` creates a missing parent directory. An
  uncommitted writer discards its staged file on garbage collection.
- `kaparoo.filesystem.staged.StagedDirectory`: the directory counterpart of
  `StagedFile`. Files are written into a temporary `workdir` in the
  destination's parent and moved into place on commit. Same context-manager /
  explicit usage and `commit` / `abort` / `path` / `committed` API (plus
  `workdir`), and the same `overwrite` / `make_parents` options. Creating a
  new directory is atomic (single rename); replacing an existing one
  (`overwrite=True`) swaps the old aside and removes it, which is not fully
  atomic. An uncommitted builder discards its staging directory on garbage
  collection.
- `kaparoo.filesystem.utils.reserve_path` / `reserve_paths`: a guard (and
  its bulk form) for a path that should not yet exist, returning it
  (optionally stringified) so the caller can create something there.
  `exist_ok` (named as in `make_dir` / `Path.mkdir`) is a
  **non-destructive** bypass (nothing is deleted) and `make_parents`
  creates the parent directory when missing.
  Raises `FileExistsError` on conflict. `reserve_paths` is fail-fast and
  takes no `root` (compose with `wrap_paths(prepend=...)`). For directory
  destinations prefer `make_dir(exist_ok=...)`; for exclusive file creation
  the stdlib `open(path, "x")` suffices.
- `clean` option on `make_dir` / `make_dirs`: when an existing *directory*
  is present, remove its contents and recreate it empty (a fresh slate).
  **Destructive**, and only ever wipes a directory -- a non-directory at
  the path still raises `NotADirectoryError`. `clean=True` makes `exist_ok`
  moot, since the directory is removed and remade.
- `kaparoo.filesystem` directory checks `dir_not_empty`,
  `dir_not_empty_unsafe`, `dirs_not_empty`, and `dirs_not_empty_unsafe`,
  the negated counterparts of the `dir_empty` series. `dirs_not_empty`
  is True only when every directory is non-empty.
- `kaparoo.utils.aggregate` module **(experimental -- the API may change in
  a later release)**: `Aggregator` for nested, pluggable metric aggregation
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

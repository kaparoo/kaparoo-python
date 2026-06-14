# Changelog

All notable changes to this project will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `kaparoo.utils.checks`: small validation guards, re-exported from
  `kaparoo.utils`. `ensure_one_of(value, options, *, name)` checks discrete
  membership (pass a `range` for an integer grid); `ensure_in_range(value, *,
  lower, upper, step, inclusive, name)` checks `int` / `float` bounds, with
  either side optional (half-open), inclusivity as a shared `bool` or a
  per-side tuple, and an optional `step` grid spacing (`base + k*step`,
  float-robust via `math.isclose`).

- `kaparoo.filters` gains an enumerable filter family: `Literal`, `OneOf`,
  `Template`, and `Without` implement an `Expandable` capability
  (`expand()`) that *lists* the finite set of names a filter matches, on
  top of the usual `matches` (`Expandable` is now a `Filter` subtype).
  `Literal` / `OneOf` are the case-sensitive, always-enumerable
  counterparts of `Equals` / `EqualsAny`; `Template` enumerates
  `template.format(*combo)` over the cartesian product of one or more
  value axes (`Template("shard_{:03d}", range(8))`,
  `Template("{}_{}.png", ["real", "fake"], range(3))`); `Without(base,
  *excluded)` is the enumerable form of `And(base, Not(...))`, expanding
  `base` minus anything the excluded filters match. They register as
  ordinary filter kinds (`"literal"` / `"one_of"` / `"template"` /
  `"without"`).
- `kaparoo.filesystem.hierarchy`: a new subpackage describing a filesystem
  tree declaratively. `File` / `Directory` nodes compose into a tree whose
  node names are `kaparoo.filters` filters — the full DSL (`Glob`,
  `Regex`, `And` / `Or` / `Not`, the enumerable `Literal` / `OneOf` /
  `Template`, ...) describes which siblings a node matches. As name sugar,
  a bare `str` becomes a `Literal` and a `list[str]` a `OneOf`, so one
  node can stand for several literally-named siblings that share a
  structure (`Directory(["train", "val"], layout)`); a sugar name must be
  a single path component (a `/` or `\` separator raises `ValueError`).
  Nodes are immutable
  value objects (`==`, `hash`, `repr`) and take a keyword-only `depth`
  (default `1`, a direct
  child) describing how far below the parent the entry sits, past
  intermediate directories of unknown name: an `int` is an exact level,
  `None` is any depth (the tree-level `**`), and a `(min, max)` tuple is
  an inclusive range (`max=None` unbounded), exposed as `min_depth` /
  `max_depth`. Each entry also takes a keyword-only `required` flag
  (default `False`) asserting it must be present. Two sibling constraints
  can sit among a directory's
  children: `Exclusive` (the present siblings may come from at most one of
  its alternatives, each a set of independent nodes on one side of the
  exclusion; `required=True` requires at least one; `on_conflict="priority"`
  resolves a multi-side conflict by declaration order — the first present
  alternative wins and the rest become `unexpected` — instead of the default
  `"error"`) and `Together` (its
  members are all-or-nothing -- all present or all absent; `required=True`
  requires all). Both take `Node`s, so constraints nest --
  `Exclusive(Together(a, b), c)` is "{a and b} or c". `File` / `Directory`
  (named, under the `Entry` base) and the constraint nodes `Exclusive` /
  `Together` (under a `Group` base that carries `required` and an
  `entries` accessor flattening to the leaf entries a constraint
  references, descending through nesting) share a common `Node` base, so a
  directory's `children` hold any `Node`. A whole tree round-trips through
  a `"node"`-discriminated dict (`to_dict` / `Node.from_dict`, mirroring
  the filter registry), so specs can be stored as JSON. The package
  depends on `kaparoo.filters` but nothing in `kaparoo.filesystem.search`.
  This first cut is the representation plus name-level semantics and the
  disk operations `match`, `validate`, `conforms`, and `scaffold` (below).
- `kaparoo.filesystem.hierarchy.match(tree, root)`: the first operation
  that applies a spec to a real filesystem. It maps each on-disk path
  under `root` (the container) to the spec node(s) it matches — by name
  filter, type (`File` ↔ file, `Directory` ↔ directory), and `depth`
  (intermediate levels of unknown name skipped) — yielding one
  `(path, node)` pair per match. It reports only what is *present*:
  `Group`s are treated as "any entry may appear," so `Exclusive` /
  `Together` enforcement and missing-`required` reporting are left to
  `validate`. A path may match several nodes (overlapping filters);
  `match` yields one pair per node (lazily, duplicates kept by default; pass
  `unique=True` to suppress identical pairs), while the companion
  `match_map(tree, root)` groups the results into a `{path: (node, ...)}`
  mapping (distinct nodes, spec-traversal order). Both take `exclude=` to
  drop paths from the results (e.g. specific cells of a `Template` product):
  an excluder — or an iterable of them, OR-combined — is a concrete
  root-relative `StrPath` or a callable taking the root-relative `Path`, and
  a dropped directory has its whole subtree pruned.
- `kaparoo.filesystem.hierarchy.validate(tree, root)`: checks a real
  directory against a spec, returning a `ValidationReport` with `matched`
  (as `match_map`), `unexpected` (paths matching no node — anything not
  matched and not an ancestor of a match, so contents of an unspecified
  directory count), `missing` (a `required` entry, or a `required`
  `Exclusive` / `Together` with nothing present), and `violations` (an
  `Exclusive` with more than one side present, or a partly-present
  `Together`). `report.ok` (and its truthiness) is `True` only when the
  last three are empty. A `required` enumerable name (`OneOf` / `Template`)
  is satisfied by at least one present match. `validate` also accepts the
  same `exclude=` as `match`, so excluded paths are dropped from `matched`
  and not reported `unexpected`. Also exports the `ValidationReport` and
  `Violation` result types.
- `kaparoo.filesystem.hierarchy.conforms(spec)`: builds a path predicate (a
  `search` predicate) that accepts a path realizing `spec`'s *top* node — a
  file matching a top `File`'s name, or a directory matching a top
  `Directory`'s name whose subtree conforms (via `validate`); a top `Group`
  is realized by any one of its alternatives / members. The path is always
  tested as the top of `spec`, never an inner node. (Checking whether a path
  or sub-spec is *contained* within a spec is a separate future capability.)
- `kaparoo.filesystem.hierarchy.scaffold(tree, root)`: the write operation —
  creates the structure a spec describes under `root` (the container, made if
  absent) and returns the newly created paths in creation order. Only
  *enumerable* nodes are materialized: a node is creatable when its `name` is
  an `Expandable` filter (`Literal` / `OneOf` / `Template` / `Without` and the
  `str` / `list[str]` sugar) **and** it sits at a fixed `depth` of 1; open
  names (`Glob`, `Regex`) and non-fixed depths are acceptance patterns, so
  they are skipped when optional and raise when `required`. `Together` creates
  all members (all-or-nothing — a non-creatable member skips the whole set
  unless `required`); `Exclusive` creates the first fully-creatable
  alternative (declaration order is the priority). Files are created empty;
  creation is idempotent (existing directories are descended, existing files
  never clobbered) and a wrong-kind path is a conflict that raises. Pass
  `dry_run=True` to return the paths that *would* be created without touching
  disk (a faithful preview that still raises on an unsatisfiable `required`).
- `kaparoo.filesystem.hierarchy.conditions`: a declarative, serializable
  condition DSL over a matched path's filesystem attributes (the `Path`-level
  counterpart of `kaparoo.filters`). `File` / `Directory` take a keyword-only
  `condition`; `validate` checks it on each matched path and lists the
  failures in `report.failed` (and `report.ok` requires it empty), while
  `match` stays purely structural. Conditions: `Size` and `ChildCount`
  (inclusive `min` / `max`), polymorphic `Empty` / `NonEmpty`, `Content` (a
  named content hook), and `And` / `Or` / `Not`. Arbitrary content checks —
  unserializable as callables — are referenced by `Content("name")` (only
  the name is stored) and supplied to `validate` / `conforms` as
  `checks={name: callable}`; an absent name is governed by
  `on_missing="error" | "skip"`. The metadata conditions round-trip through
  `to_dict` / `from_dict`.
- `kaparoo.utils.aggregate` gains store-all reductions
  for non-decomposable statistics: `Stored(reduce)` keeps every
  `(value, weight)` pair and applies `reduce` to the full sample on `result`
  (O(n) memory -- a documented escape hatch from the constant-memory
  contract), with `Median()` and `Quantile(q)` built on top (a weighted,
  non-interpolating quantile). Unlike the online reductions their state is a
  mutable list, so a `state()` snapshot of such a metric changes under
  further `update`s. Also adds an `OptionalFold` base (the `None`-seeded fold
  shared by `Min` / `Max` / `Last`, subclassed by supplying a single
  `_combine`).

### Changed

- `kaparoo.utils.aggregate` is no longer experimental: the `Aggregator` /
  `Reduction` API is now covered by the project's SemVer guarantees. No code
  change -- the "work in progress" notes are dropped from the module docstring
  and `kaparoo/utils/README.md`.
- Moved the filter DSL from `kaparoo.filesystem.search.filters` to the new
  top-level `kaparoo.filters`. The filters are a filesystem-agnostic
  string-matching DSL, now shared beyond `search`. **Breaking**: update
  imports from `kaparoo.filesystem.search.filters` to `kaparoo.filters`
  (e.g. `from kaparoo.filters import Glob, And`). Class names, serialized
  format, and matching behavior are unchanged.
- `kaparoo.filters` serialization is now a template method: `Filter.to_dict`
  injects the `"kind"` discriminator (stamped onto the class as `_kind` by
  `register_filter`) and subclasses supply only their own fields via a new
  abstract `_payload`. **Breaking** for *custom* `Filter` subclasses —
  implement `_payload` (the kind-less fields) instead of `to_dict`; the
  serialized output of the built-in filters is unchanged. `AndFilter` /
  `OrFilter` now share a `NaryLogicalFilter` base.
- Faster filter matching: `EqualsAny` and `OneOf` test a precomputed
  `frozenset` (O(1) rather than a linear tuple scan -- `OneOf` keeps its
  ordered tuple for `expand`); `Template` matches against its expanded names
  materialized once; `Glob` translates and compiles its pattern to a
  `re.Pattern` once at construction (like `Regex`), skipping `fnmatch`'s
  per-call cache lookup; and `search` skips the per-directory path
  stringification when no `part_filter` is given.
- `kaparoo.data.sequences.ConcatSequence` now batch-delegates: `get_items` /
  `get_metas` group the requested indices per source and issue one call per
  source (results scattered back into request order), so a source's own
  batch optimization is used instead of a per-index `get_item` loop. This
  completes the bulk-delegation already done by the other composers; it
  matters only when a source overrides `get_items` with a real batch read
  (order, duplicates, and negative / out-of-range handling are unchanged).
- `kaparoo.filesystem.ensure_file_exists` / `ensure_dir_exists` test the
  type (`is_file` / `is_dir`) before falling back to `exists()`, halving the
  `stat` calls on the success path (and `ensure_dir_exists` drops a redundant
  post-`mkdir` re-check). Behavior is unchanged.
- `kaparoo.utils.unwrap_or_defaults` / `unwrap_or_factories` now annotate
  their return as `list[T]` (was `Sequence[T]`), matching what they have
  always returned. A type-hint-only refinement; callers relying on the
  wider `Sequence` type are unaffected.
- `kaparoo.utils.timer`: merged the internal `BaseTimer` into `Timer`, so
  `SpanTimer` now subclasses `Timer` (it shares `Timer`'s `elapsed` and
  machinery, adding spans). The duplicate `_finalize` is gone.
  `isinstance(span_timer, Timer)` is now `True`, and `BaseTimer` is no
  longer importable (it was never in `__all__`).
- `kaparoo.utils.timer`: the exposed timer state is now read-only.
  `Timer.unit` / `ndigits` / `elapsed` and `SpanTimer.on_same_label` /
  `records` are properties without setters, matching the read-only-property
  convention used elsewhere in the library. **Breaking**: `records` now
  returns a `tuple` snapshot rather than the live `list` (iteration,
  indexing, and `len` are unchanged; `.append` / `+=` / `isinstance(...,
  list)` are not), and assigning to any of these attributes now raises
  `AttributeError`.

### Fixed

- `Aggregator.merge` adopted a metric present only in the other tracker by
  sharing its state object; for a store-all reduction (`Median` / `Quantile`
  / `Stored`) a later `update` on the absorbing tracker then mutated the
  source's samples too. It now copies the adopted state, and merging a tracker
  into itself is a no-op.

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

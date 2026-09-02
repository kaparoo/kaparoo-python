# Changelog

All notable changes to this project will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `kaparoo.filesystem.STAGING` (re-exported from `kaparoo.filesystem`): a
  `Filter` matching the leaf names `StagedFile` / `StagedDirectory` stage
  under, for collecting what an interrupted run left behind. It matches the
  in-flight staging (`.report.json.a1b2c3d4.tmp`) and the displaced-original
  backup a directory replace strands on a crash between its two renames
  (`.dataset.a1b2c3d4.tmp.old`) -- the latter is the one nothing else
  collects. Intended as a `name_filter`, not an `exclude` rule, and a match
  reports only that a staging is there, never that it is dead: a concurrent
  writer's staging is indistinguishable by name.

## [0.13.1] - 2026-08-09

### Added

- `kaparoo.filesystem.WalkKwargs`: the `search_*` keyword set without
  `predicate`, for a wrapper that supplies or retypes `predicate` itself and
  forwards the remaining walk keys. `SearchKwargs` now subclasses it.
- `FileListSequence.get_name`: the leaf name of the file at an index, read
  from the stored string without constructing a `Path`. Inherited by
  `FileFolderSequence`.

### Changed

- `kaparoo.filesystem.contains` gained a keyword-only `kind`
  (`"any"` | `"dir"` | `"file"`, default `"any"`), selecting whether the held
  entry must be a directory, a file, or either. The default keeps the existing
  existence check, so nothing breaks.

## [0.13.0] - 2026-08-09

### Added

- `kaparoo.filesystem.search.selection.is_spec_file` and `SPEC_FILE_SUFFIXES`
  (re-exported from `kaparoo.filesystem.search` and `kaparoo.filesystem`).
  `SPEC_FILE_SUFFIXES` is the tuple of file suffixes `select` /
  `resolve_selector` read as a spec file (`(".json", ".txt")`), and
  `is_spec_file(source)` reports whether a value would be read as one, using
  the same case-insensitive `PurePath(...).suffix` test the loader applies, so
  a leading-dot name such as `.json` (which has no suffix) is an inline name,
  not a file. Lets a caller tell in advance whether a string will be loaded
  from disk or matched inline.
- `kaparoo.utils.resolve_enum` (re-exported from `kaparoo.utils`): resolve a
  string to a member of an `Enum` by member name, case-insensitively unless
  `case_sensitive=True`. `exclude` rejects the given members like unknown
  names and keeps them out of the error message.
- `kaparoo.utils.literal_values` (re-exported from `kaparoo.utils`): return the
  values a `Literal` admits, resolving a PEP 695 `type X = Literal[...]` alias
  through `__value__` (which `get_args` does not see through), and raising
  `TypeError` on anything that does not resolve to a `Literal`.
- `kaparoo.utils.quantify` (re-exported from `kaparoo.utils`): return `count`
  followed by `noun`, pluralized for every count but one. `plural` overrides
  the default `noun + "s"` and covers an irregular plural (a stem change or a
  replacement) that a suffix cannot.
- `kaparoo.data.sequences.DataSequence.__getitems__`: a batch-fetch method
  that delegates to `get_items`, so a subclass's `get_items` override drives
  whole-batch access.
- `kaparoo.filesystem.contains`: a predicate factory returning
  `Callable[[Path], bool]` that tests whether `path / subpath` exists,
  composable as a `search_*` `predicate`.
- `kaparoo.filesystem.search.SearchKwargs` (re-exported from
  `kaparoo.filesystem`): a `TypedDict` of the keyword set `search_paths` /
  `search_files` / `search_dirs` share, so a wrapper can accept and forward it
  as `**options: Unpack[SearchKwargs]` without re-declaring each key.
- `descend` on `search_paths` / `search_files` / `search_dirs`: a
  `Callable[[Path], bool]` deciding whether to visit a sub-directory. A
  directory that fails it is still offered to the filters and may be returned,
  but its subtree is not walked. Unlike `exclude` it only prunes, never drops.
- `kaparoo.filesystem.prune_upward(folder, stop)`: remove `folder` and each
  parent it leaves empty, climbing up to but not `stop`. `stop` is a
  strict-ancestor boundary (a `folder` not under `stop`, including
  `folder == stop`, is left untouched), and each `rmdir` runs without a
  preceding emptiness check, so a non-empty, missing, wrong-kind, or
  unpermitted directory halts the climb. Destructive.

### Changed

- `kaparoo.utils.ensure_one_of` now binds its type parameter from `options`
  alone (`value` is typed `object`), so the return type carries `options`'
  narrowing: `ensure_one_of(text, POLICIES)` with a `Literal` tuple `POLICIES`
  returns that `Literal` rather than `str`. Runtime behavior is unchanged; a
  `value` whose type is unrelated to `options` no longer fails statically (it
  still raises at runtime).

## [0.12.0] - 2026-07-30

### Added

- `kaparoo.filters.selection`: `select` and `resolve_selector` (plus the
  `Selector` type), re-exported from `kaparoo.filters`. `select` keeps the
  items an `include` spec matches, then drops the ones an `exclude` spec
  matches (so on an overlap `exclude` wins); each item is named by a `key`
  callable and both specs default to no restriction. A spec is one of, all
  normalized to a single `kaparoo.filters` filter: a `str` (an exact name) or
  a `Sequence` of them; a `FilterDict` (e.g. `{"kind": "glob", "pattern":
  "a/*"}`) or a sequence mixing name strings and `FilterDict`s; or a `Filter`
  instance. `resolve_selector` is that shared front end, exposed so `include`
  / `exclude` can be resolved (and applied) independently. When a spec is
  an exact-name set (a string or a string list) a name matching no item raises
  `ValueError` (a typo says so instead of silently selecting nothing), while
  an open pattern (`Glob` / `Regex`) matching nothing is allowed; the
  typo check lives in `select`, not `resolve_selector`. Both take an optional
  `normalize` callable applied to every exact-name string before matching.
  This base is filesystem-agnostic: it resolves only in-memory specs and never
  touches the disk.
- `kaparoo.filesystem.search.selection`: the path-aware extension of the
  above (`select` / `resolve_selector` / `Selector`, re-exported from
  `kaparoo.filesystem.search` and `kaparoo.filesystem`). It adds the two
  filesystem-flavored features the base leaves out: a spec may also be a
  `.json` file (a `FilterDict` object or an array) or a `.txt` file listing
  one subpath per line (blank lines and `#` comments skipped). A bare string
  is read as a file only when it ends in `.json` / `.txt`, otherwise it is a
  single inline subpath, and exact-name subpaths are normalized to POSIX
  `/`. Everything else delegates to `kaparoo.filters.selection`. Unlike the
  search entry points' `exclude=`, which prunes a subtree during the walk,
  `select` filters an already-materialized collection, so it also works on
  items that are not paths.

## [0.11.1] - 2026-07-23

### Changed

- Consolidated the sequence index-normalization logic onto
  `kaparoo.data.sequences.DataSequence._normalize_index`. The private
  module-level `_resolve_index(index, length)` in
  `kaparoo.data.sequences.composers` and the duplicate `_normalize_index`
  wrappers on `WindowedSequence` / `ZippedSequence` are gone, replaced by the
  single inherited base method, which reads `len(self)` instead of taking a
  `length`. Behavior, the raised `IndexError`, and its message are unchanged,
  and subclasses calling `self._normalize_index(...)` (as the `data` README
  shows) keep working untouched. Being on the base, the protected hook is now
  inherited by every `DataSequence` rather than only the composers, so it is
  available when subclassing the base or the file templates; an empty
  sequence raises `IndexError` rather than dividing by zero.
  `SlicedSequence` still deliberately opts out, indexing its `indices` tuple
  directly.

## [0.11.0] - 2026-07-15

### Added

- `kaparoo.filters.AnyFilter` / `Any`: a constant filter that matches every
  string -- the top element of the filter lattice. It reads as an explicit
  "match anything" placeholder (clearer and cheaper than `Glob("*")`, with no
  regex to compile or run) and acts as the identity of `And` / absorbing
  element of `Or`. It is fieldless (all instances are equal), serializes as
  `{"kind": "any"}`, and is deliberately not `Expandable` -- so as a
  `hierarchy` node name it is an open, acceptance-only pattern like `Glob`.
  Lives in the new `kaparoo/filters/constant.py` module.
- `kaparoo.utils.fold_optional` / `fold_optionals`: collapse a `T | None`
  into a possibly different type `R` by branching on presence -- apply
  `transform` to a present value, otherwise return `default`. Unlike the
  substitute / unwrap helpers (which keep the input type `T`), the two
  branches may yield different values and types. `transform` runs only when
  the value is present, so a side effect it carries never fires on the None
  branch. `fold_optionals` applies the same branch element-wise over a
  sequence and returns a `list`.

## [0.10.0] - 2026-07-07

### Added

- `kaparoo.filesystem.ensure_file_exists` / `ensure_files_exist` gain an
  `ext=` argument (a single extension or an iterable of acceptable ones,
  each with or without a leading dot, matched case-insensitively) that also
  requires the file's final suffix to be accepted, delegating to
  `kaparoo.filesystem.utils.ensure_file_extension`. The pure extension check
  runs *before* the filesystem is consulted, so a wrong or missing suffix
  raises `UnsupportedExtensionError` (a `ValueError` subclass) even for a path
  that does not exist. `ext=None` (the default) keeps the previous behavior.
  For `ensure_files_exist` the accepted set is broadcast to every path (not
  paired positionally with `paths`).

### Changed

- **Lowered the minimum Python version from 3.14 to 3.13.** No code change --
  the package's real floor is the PEP 696 type-parameter defaults it uses
  (`class C[T, M = None]`, ...), which are 3.13 syntax; nothing depended on a
  3.14-only feature. CI now runs the toolchain across 3.13 and 3.14. Widening
  the supported range is non-breaking for existing 3.14 users.

## [0.9.1] - 2026-06-22

### Changed

- `kaparoo.filesystem.hierarchy.locate` now yields in a fully deterministic
  order: each directory's entries sorted by name *and* subdirectories descended
  in that same order (so `locate_map`'s iteration order is deterministic too).
  Previously only siblings within a level were sorted; the order across sibling
  subtrees followed the OS directory order, so an open-depth match could vary
  by filesystem. `validate`'s report was already sorted and is unchanged.
- `kaparoo.utils.aggregate.Aggregator.update` no longer adds `weight` to the
  grand total for an empty `values={}` batch -- with nothing folded in, the
  call contributes no weight (the `weight` property counts weight actually
  folded in). A non-empty update is unchanged.

### Fixed

- `kaparoo.filesystem.make_dirs` now detects a duplicated path in its
  validate-first pass and raises `FileExistsError` *before* creating anything,
  under strict-create (`exist_ok=False`, `clean=False`). Previously the second
  occurrence's `mkdir` failed only after the first had already created the
  directory, leaving a partial side effect. A repeat stays harmless (idempotent)
  under `exist_ok=True` or `clean=True` and is still accepted there.
- `kaparoo.filesystem.wrap_path` / `wrap_paths` now reject a Windows
  drive-relative `prepend` target or `append` value (e.g. `C:foo` -- a drive
  with no root) with `ValueError`, instead of silently discarding the other
  component (`Path("base", "C:foo")` collapses to `Path("C:foo")`). The guard
  moved from `os.path.isabs` to a `Path.anchor` check, which is platform-aware:
  `C:foo` stays an ordinary relative name on POSIX and is unaffected.

## [0.9.0] - 2026-06-22

### Added

- `kaparoo.filesystem.utils.normalize_extension` / `normalize_extensions` /
  `file_extension`: extension-string helpers. `normalize_extension` strips
  surrounding whitespace and leading dots (`" .BIN " -> "BIN"`), keeping case
  unless `lowercase=True`; `normalize_extensions` maps it over an iterable
  (threading `lowercase`; empties and duplicates deliberately kept -- that
  policy is the caller's). `file_extension(path)`
  returns the path's last (up to) `level` suffix(es), dot-joined and
  normalized -- `level=2` yields `"tar.gz"` from `data.tar.gz`,
  `lowercase=False` keeps case, no suffix gives `""`. `ensure_file_extension`
  now builds on these. All are re-exported from the top-level
  `kaparoo.filesystem` namespace.
- `kaparoo.filesystem.exceptions.UnsupportedExtensionError` (also re-exported
  from `kaparoo.filesystem`): a `ValueError` subclass for an extension that is
  none of the supported ones. The constructor normalizes `supported` (strips
  surrounding whitespace and leading dots, case preserved), de-duplicates it,
  and drops empties; an optional `kind` labels the message, rendering e.g.
  `unsupported extension 'gif' (supported: 'jpg', 'png')` (with ` for <kind>`
  inserted when `kind` is given). It exposes `ext` / `supported` / `kind`.
- `kaparoo.filesystem.hierarchy.scaffold` gains two options. `on_create` is a
  callback `on_create(path, file_node)` run once for each file *actually*
  created -- the seam for writing a file's content (scaffold otherwise leaves
  an empty skeleton); it is not called for an untouched existing file, under
  `dry_run`, or with `dirs_only`. `dirs_only=True` creates only the directory
  skeleton, skipping every file (including `required` ones); pairing it with
  `on_create` raises `ValueError`.
- `kaparoo.filesystem.hierarchy.Entry.is_direct_child`: a read-only property,
  `True` only when the entry is pinned to exactly `depth` 1 (`min_depth` and
  `max_depth` both 1) -- the default, unranged position `scaffold` requires to
  create a node.

### Changed

- `kaparoo.filesystem.utils.ensure_file_extension` now raises the new
  `UnsupportedExtensionError` (a `ValueError` subclass, so existing
  `except ValueError` still catches it) instead of a plain `ValueError` when a
  path's final suffix is none of the accepted extensions. The empty-`ext`
  argument still raises a plain `ValueError`.
- `kaparoo.filesystem.hierarchy.scaffold` now raises `NotADirectoryError` (a
  file where a directory is described) or `NotAFileError` (a directory where a
  file is described) for a wrong-kind conflict, instead of a plain `ValueError`,
  aligning with the rest of `kaparoo.filesystem`. **Breaking** for callers that
  caught these as `ValueError` -- `NotADirectoryError` / `NotAFileError` are
  `OSError` subclasses, not `ValueError`.

### Fixed

- `kaparoo.utils.SpanTimer.measure` now raises a clear, actionable `RuntimeError`
  when its block ends while still paused (a `pause()` left open across the block
  boundary), pointing to `suspend()`, instead of the misleading "Cannot record a
  lap while paused" it surfaced from the trailing `lap`.

## [0.8.0] - 2026-06-19

### Added

- `kaparoo.filesystem.search` (`search_paths` / `search_files` /
  `search_dirs`) gains an `exclude=` argument: paths to skip, as a `StrPath`
  (absolute under `root`, or root-relative), a `Filter` (matched on the
  root-relative POSIX path), a callable on the candidate `Path` (the real,
  filesystem-valid path), or an iterable of these (OR-combined). An
  excluded *directory* is **pruned** -- its subtree is never walked -- which
  `name_filter` cannot do (a directory failing `name_filter` is still
  descended). The excluder engine is shared with `kaparoo.filesystem.hierarchy`
  via the new internal `kaparoo.filesystem.exclude` module.

- `kaparoo.utils.checks`: small validation guards, re-exported from
  `kaparoo.utils`. `ensure_one_of(value, options, *, name)` checks discrete
  membership (pass a `range` for an integer grid); `ensure_in_range(value, *,
  lower, upper, step, inclusive, name)` checks `int` / `float` bounds, with
  either side optional (half-open), inclusivity as a shared `bool` or a
  per-side tuple, and an optional `step` grid spacing (`base + k*step`,
  float-robust via `math.isclose`).

- `kaparoo.filters` gains an enumerable filter family: `LiteralFilter`,
  `OneOfFilter`, `TemplateFilter`, and `WithoutFilter` (with short aliases
  `Literal` / `OneOf` / `Template` / `Without`, matching the rest of the
  package) implement an `Expandable` capability (`expand()`) that *lists*
  the finite set of names a filter matches, on top of the usual `matches`
  (`Expandable` is now a `Filter` subtype).
  `Literal` / `OneOf` are the case-sensitive, always-enumerable
  counterparts of `Equals` / `EqualsAny`; `Template` enumerates
  `template.format(*combo)` over the cartesian product of one or more
  value axes (`Template("shard_{:03d}", range(8))`,
  `Template("{}_{}.png", ["real", "fake"], range(3))`); `Without(base,
  *excluded)` is the enumerable form of `And(base, Not(...))`, expanding
  `base` minus anything the excluded filters match. They register as
  ordinary filter kinds (`"literal"` / `"one_of"` / `"template"` /
  `"without"`) and each gets a matching TypedDict in
  `kaparoo.filters.types` (`LiteralFilterDict`, `OneOfFilterDict`,
  `TemplateFilterDict`, `WithoutFilterDict`) for statically-checked dict
  authoring.
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
  (default `False`) asserting it must be present. A `Directory` additionally
  takes a keyword-only `allow_extra` (default `False`, a `bool | Filter`):
  `True` makes `validate` / `conformer` ignore its on-disk contents that match
  none of its `children` (instead of reporting them `unexpected`), while a
  `Filter` ignores only those whose name it matches; a matched subdirectory
  keeps its own strictness. Two sibling constraints
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
  disk operations `locate`, `validate`, `conformer`, and `scaffold` (below).
- `kaparoo.filesystem.hierarchy.locate(tree, root)`: the first operation
  that applies a spec to a real filesystem. It maps each on-disk path
  under `root` (the container) to the spec node(s) it matches — by name
  filter, type (`File` ↔ file, `Directory` ↔ directory), and `depth`
  (intermediate levels of unknown name skipped) — yielding one
  `(path, node)` pair per match. It reports only what is *present*:
  `Group`s are treated as "any entry may appear," so `Exclusive` /
  `Together` enforcement and missing-`required` reporting are left to
  `validate`. A path may match several nodes (overlapping filters);
  `locate` yields one pair per node (lazily, duplicates kept by default; pass
  `unique=True` to suppress identical pairs), while the companion
  `locate_map(tree, root)` groups the results into a `{path: (node, ...)}`
  mapping (distinct nodes, spec-traversal order). Both take `exclude=` to
  drop paths from the results (e.g. specific cells of a `Template` product):
  an exclude rule — or an iterable of them, OR-combined — is a `StrPath`
  (absolute under `root`, or root-relative), a `kaparoo.filters` `Filter`
  matched on the root-relative POSIX string (the serializable counterpart of
  a callable), or a callable taking the candidate's own `Path` (the real,
  filesystem-valid path, so it may inspect the file), and a dropped directory
  has its whole subtree pruned. Pass `root_as_top=True` to
  treat `root` as the realized top node itself (you point at the top
  directly) rather than its container; the top must be an `Entry` (a `Group`
  raises `TypeError`) and `root` realizes it only when its leaf name / kind
  match, otherwise nothing is yielded.
- `kaparoo.filesystem.hierarchy.validate(tree, root)`: checks a real
  directory against a spec, returning a `ValidationReport` with `matched`
  (as `locate_map`), `unexpected` (paths matching no node — anything not
  matched and not an ancestor of a match, so contents of an unspecified
  directory count), `missing` (a `required` entry, or a `required`
  `Exclusive` / `Together` with nothing present), and `violations` (an
  `Exclusive` with more than one side present, or a partly-present
  `Together`). `report.ok` (and its truthiness) is `True` only when the
  last three are empty. A `required` entry is satisfied by one present match
  — an enumerable name (`OneOf` / `Template`) by any one listed name, an open
  name (`Glob` / `Regex`) by any one matching path. `validate` also accepts the
  same `exclude=` as `locate`, so excluded paths are dropped from `matched`
  and not reported `unexpected`. It also takes the same `root_as_top=True` to
  validate `root` as the realized top entry itself (a `Group` top raises
  `TypeError`); a leaf name / kind mismatch reports the top as `missing`
  without descending. A top-level `allow_extra` (`bool | Filter`) applies
  blanket leniency to every directory (and the container `root`), as if each
  carried it, combined with each `Directory`'s own. Also exports the
  `ValidationReport` and `Violation`
  result types. Two reports combine with `+` (problem lists concatenate and
  `matched` merges, so the result is `ok` only when both are) for accumulating
  independent validations.
- `kaparoo.filesystem.hierarchy.conformer(spec)`: builds a path predicate (a
  `search` predicate) that accepts a path realizing `spec`'s *top* node — a
  file matching a top `File`'s name, or a directory matching a top
  `Directory`'s name whose subtree conforms (via `validate`); a top `Group`
  is realized by any one of its alternatives / members. The path is always
  tested as the top of `spec`, never an inner node. Takes the same
  `allow_extra` as `validate` to accept a top whose subtree carries extra,
  unspecified entries. (Checking whether a path or sub-spec is *contained*
  within a spec is a separate future capability.)
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
  `locate` stays purely structural. Conditions: `Size` (a file's bytes),
  `ChildCount` (a directory's entries -- all, or only files / only
  directories via `only`), and `TreeSize` (a directory's
  recursive content size) -- all inclusive `min` / `max`; polymorphic
  `Empty` / `NonEmpty`; `Content` (a named content hook); and `And` / `Or`
  / `Not`. Each declares the entry kind(s) it can check (`Size` file-only,
  `ChildCount` / `TreeSize` directory-only, the rest both; a composite is
  the intersection of its children), so a kind-mismatched `condition`
  raises at construction. Arbitrary content checks —
  unserializable as callables — are referenced by `Content("name")` (only
  the name is stored) and supplied to `validate` / `conformer` as
  `hooks={name: callable}`; an absent name is governed by
  `on_missing="error" | "skip"`. The metadata conditions round-trip through
  `to_dict` / `from_dict`.
- `Entry.accepts_depth(depth)` / `Entry.accepts_kind(path)` / `Entry.matches(path)`:
  predicate methods on the `Entry` base. `accepts_depth(depth)` returns `True`
  when `depth` falls within the entry's inclusive `[min_depth, max_depth]`
  range (`max_depth=None` is unbounded). `accepts_kind(path)` returns `True`
  when the on-disk kind of `path` matches the entry's own kind (`File` ↔ file,
  `Directory` ↔ directory). `matches(path)` combines the name filter with
  `accepts_kind` -- `True` when `path`'s leaf name and on-disk kind both fit
  the entry (depth, a positional concern, is left to `accepts_depth`).
  `accepts_condition(path, resolver)` is `True` when the entry's attribute
  `condition` is absent or holds for `path` (the resolver supplies `Content`
  hooks).
- `kaparoo.filesystem.hierarchy.group.flatten_entries(nodes)` /
  `max_depth_of(nodes)`: both accept a single `Node` **or** an iterable of
  nodes (`Node | Iterable[Node]`), so callers holding a single node need not
  wrap it in a list. `flatten_entries` recursively gathers the leaf `Entry`
  nodes (groups descended, result always a flat tuple). `max_depth_of` returns
  the deepest level any node requires (once flattened), `None` if any entry's
  depth is unbounded, and `1` for an empty input.
- `kaparoo.filesystem.units`: byte-size unit constants -- decimal `KB` / `MB`
  / `GB` / `TB` (powers of 1000) and binary `KIB` / `MIB` / `GIB` / `TIB`
  (powers of 1024). They are plain `int` multipliers for readable file-size
  values, e.g. `Size(max=5 * MB)` or `TreeSize(max=2 * GIB)`. Imported
  explicitly from `kaparoo.filesystem.units` -- deliberately **not**
  re-exported at the `kaparoo.filesystem` top level, so a bare `MB` / `GB`
  always names its convention.
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
- `kaparoo.filters` filters now render a concise, constructor-style `repr`
  under their short alias name instead of the default dataclass field dump
  -- `Equals('README')` rather than
  `EqualsFilter(pattern='README', case_sensitive=True)`. The displayed name
  drops the canonical `Filter` suffix (`EqualsFilter` -> `Equals`,
  `LiteralFilter` -> `Literal`), the primary value (`pattern` / `patterns`
  / `child` / `children` / `name` / `names`) is shown unlabeled, and
  `case_sensitive` appears only when `False` (its non-default). This also
  shortens anything that embeds a filter `repr`, such as
  `kaparoo.filesystem.hierarchy` node reprs (`File(Literal('a'))`). A
  `Template` axis that is an integer arithmetic progression is shown as the
  equivalent `range(...)` (`Template('v{}', range(0, 10))`), since `range`
  is a valid axis input. `repr` is informational only; equality, hashing,
  and serialization are unchanged.
- `kaparoo.filesystem.stringify_path` / `stringify_paths` now normalize to
  POSIX form via `Path.as_posix()` on every platform, replacing the
  Windows-only backslash substitution. Output is therefore normalized
  (redundant `/` and `.` segments collapsed), and a path trimmed to nothing
  stringifies to `"."` consistently. An `after` mismatch now raises a clearer
  `ValueError` (`"path ... does not start with ..."`) instead of surfacing
  pathlib's raw `"is not in the subpath of"` message.
- `kaparoo.filesystem` bulk helpers now annotate their return as the concrete
  `list[...]` they already build, rather than the abstract `Sequence[...]`:
  `stringify_paths` / `wrap_paths` / `reserve_paths`, `make_dirs`,
  `ensure_files_exist` / `ensure_dirs_exist`, and `Search.run` / `search_paths`
  / `search_files` / `search_dirs`. Each returns an eager, caller-owned list,
  so the `Sequence` abstraction bought a backing-type freedom these builders
  never exercise. Narrowing `Sequence` -> `list` is non-breaking (callers typed
  against the wider `Sequence` are unaffected); genuinely lazy results stay
  `Iterator` (`hierarchy.locate`) and immutable views stay `tuple`.

### Removed

- **Breaking:** the deprecated `get_paths` / `get_files` / `get_dirs`
  accessors (and the internal `search.deprecated` module) are removed --
  deprecated since 0.2.1, superseded by `search_paths` / `search_files` /
  `search_dirs`. Migration: a `pattern=` glob maps to `name_filter` (with
  `min_depth` / `max_depth` for `**`, or a `part_filter` for literal
  directory segments); `excludes=` maps to `exclude` (which prunes an
  excluded directory's subtree) or a `predicate` to drop only the entry;
  `condition=` maps to `predicate`; `recursive=True` is the default
  (unbounded depth).

### Fixed

- `kaparoo.filters.GlobFilter` (`Glob`) case-insensitive matching now uses
  `re.IGNORECASE` instead of casefolding the pattern and target, matching
  `RegexFilter`. Casefold is not length-preserving, so `?` / `[seq]` no longer
  desync on a character whose fold expands (e.g.
  `Glob("?", case_sensitive=False)` now matches `"ß"`). The stored / serialized
  `pattern` of a case-insensitive glob is no longer casefolded.
- `kaparoo.filters.Filter.parse` / `Filter.from_dict` raise a clear `TypeError`
  on a non-mapping argument (previously a confusing `AttributeError`), and a
  `{"kind": null}` dict reports an unknown kind rather than a missing one.
- `Aggregator.merge` adopted a metric present only in the other tracker by
  sharing its state object; for a store-all reduction (`Median` / `Quantile`
  / `Stored`) a later `update` on the absorbing tracker then mutated the
  source's samples too. It now copies the adopted state, and merging a tracker
  into itself is a no-op.
- `kaparoo.filesystem.search` no longer re-exports the whole
  `kaparoo.filters` namespace (`Filter`, `Glob`, `register_filter`, ...). The
  independent `filters` package is the canonical import; `search` now exports
  only its own `search_paths` / `search_files` / `search_dirs`.

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

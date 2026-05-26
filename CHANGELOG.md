# Changelog

All notable changes to this project will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No entries yet._

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
- `wrap_path` / `wrap_paths` with `prepend` and `append` keyword arguments.
- `before` parameter on `stringify_path` / `stringify_paths` for tail
  trimming.
- `stringify` parameter on `make_dir` / `make_dirs`.
- `README.md` module overview; `CHANGELOG.md`; `TODO.md`.

### Changed

- Toolchain migrated to a copier-based template with `uv` + `ty` +
  `ruff` + `pytest`.
- Adopted PEP 695 type parameters across the package; removed the
  `kaparoo.utils.types` module.
- `Search` is now stateless: configuration moved from `__init__` to
  `run`.
- Renamed `prepend_path` / `prepend_paths` → `wrap_path` / `wrap_paths`.
- Renamed `LapTimer.dup_mode` → `on_same_label` with outcome-based
  values (`"merge"` / `"separate"` / `"reject"`).
- Renamed `BaseFilter` → `Filter` (top-level abstract), and the
  former string-pattern `Filter` → `PatternFilter`.
- Renamed `LapTimer.total_elapsed` → `LapTimer.elapsed` for parity
  with `Timer.elapsed`.
- Renamed the `matches()` parameter `s` → `target`.
- Made `root` keyword-only in `dirs_empty` / `dirs_empty_unsafe`.
- `RegexFilter` pre-compiles its pattern at construction (bypasses
  `re`'s internal pattern cache).
- `MultiPatternFilter` patterns are `casefold`-normalized and
  deduplicated once at construction.
- `_filter_names` short-circuits when no filter is supplied.

### Deprecated

- `get_paths`, `get_files`, `get_dirs` now emit `DeprecationWarning`;
  use `search_paths` / `search_files` / `search_dirs`.

### Removed

- `LapTimer.final` attribute (use `LapTimer.elapsed` and
  `LapTimer.records`).
- `Filter.include` polarity field (use `NotFilter` for logical negation).
- `num_samples` parameter of `get_paths()`.

### Fixed

- `LapTimer.on_same_label` is validated at construction time.
- `ensure_dirs_exist`: `make` mode validation no longer skipped when
  `paths` is empty.
- Incorrect exception name in `dirs_empty` docstring.
- Typo in `DirectoryNotFoundError` docstring.

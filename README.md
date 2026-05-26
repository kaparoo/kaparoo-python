# kaparoo-python

[![PyPI version](https://img.shields.io/pypi/v/kaparoo-python.svg)](https://pypi.org/project/kaparoo-python/)
[![Downloads](https://pepy.tech/badge/kaparoo-python)](https://pypi.org/project/kaparoo-python/)
[![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)

*Personally common and useful Python features.*

## 📦 Installation

Requires Python 3.14+.

```bash
# With uv (recommended)
uv add kaparoo-python

# With pip
pip install kaparoo-python
```

## 🧩 Modules

### `kaparoo.filesystem`

`pathlib`-based filesystem helpers.

- **`existence`** — single-path checks (`path_exists`, `file_exists`,
  `dir_exists`) plus multi-path (`paths_exist`, `files_exist`,
  `dirs_exist`) and `ensure_*` variants (`ensure_path_exists`,
  `ensure_file_exists`, `ensure_dir_exists`, and their multi forms).
- **`directory`** — `make_dir` / `make_dirs`, `dir_empty` / `dirs_empty`,
  plus `_unsafe` versions that skip existence checks.
- **`utils`** — `stringify_path` / `stringify_paths` (with optional
  `after` / `before` trimming) and `wrap_path` / `wrap_paths` (with
  `prepend` / `append`).
- **`exceptions`** — `DirectoryNotFoundError`, `NotAFileError`.
- **`types`** — `StrPath`, `StrPaths` type aliases.

### `kaparoo.filesystem.search`

Filesystem traversal with composable filters.

- **Entry points** — `search_paths`, `search_files`, `search_dirs`. Each
  walks a root directory and returns matching paths, accepting
  `part_filter` / `name_filter` / `predicate` / `min_depth` /
  `max_depth` / `ordered` / `stringify`.
- **Pattern filters** — `Equals`, `StartsWith`, `EndsWith`, `Contains`,
  `Regex`, `Glob` (TitleCase aliases of the canonical `*Filter` classes).
- **Multi-pattern filters** — `EqualsAny`, `StartsWithAny`,
  `EndsWithAny`, `ContainsAny` for any-of matching against a tuple of
  patterns.
- **Logical filters** — `And`, `Or`, `Not` for arbitrary boolean
  composition; nest freely with the pattern filters.
- **Deprecated** — `get_paths`, `get_files`, `get_dirs`. Use `search_*`
  instead; the legacy functions emit `DeprecationWarning`.

### `kaparoo.utils`

- **`timer`** — `Timer` (single-shot) and `LapTimer` (multi-lap)
  context-manager / decorator timers, built on `time.perf_counter_ns`.
  Both expose `.elapsed` once the block exits, plus `pause` / `resume`
  / `suspend` for excluding time intervals from measurement. `LapTimer`
  additionally records named `LapRecord`s via `.lap(label)` and exposes
  per-label aggregation via `.summary`.
- **`optional`** — `Optional[T]` unwrapping helpers: `replace_if_none`,
  `factory_if_none`, and `unwrap_or_default` / `unwrap_or_factory`
  (plus their multi variants `unwrap_or_defaults` / `unwrap_or_factories`).

## 📋 TODO

See [TODO.md](./TODO.md) for tracked open items.

## 📜 Changelog

See [CHANGELOG.md](./CHANGELOG.md) for the version history.

## ⚖️ License

This project is distributed under the terms of the [MIT](./LICENSE) license.

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

- **`existence`** — existence checks (`*_exists`) and `ensure_*` validators.
- **`directory`** — `make_dir(s)`, `dir_empty(s)` (with `_unsafe` variants).
- **`utils`** — `stringify_path(s)`, `wrap_path(s)`.
- **`exceptions`** — `DirectoryNotFoundError`, `NotAFileError`.
- **`types`** — `StrPath`, `StrPaths`.

### `kaparoo.filesystem.search`

Filesystem traversal with composable filters.

- **Entry points** — `search_paths`, `search_files`, `search_dirs`.
- **Pattern filters** — `Equals`, `StartsWith`, `EndsWith`, `Contains`,
  `Regex`, `Glob`.
- **Multi-pattern filters** — `EqualsAny`, `StartsWithAny`, `EndsWithAny`,
  `ContainsAny`.
- **Logical filters** — `And`, `Or`, `Not`.
- **Serialization** — `Filter.to_dict()` / `Filter.from_dict()` round-trip
  via a `"kind"` discriminator; `Filter.parse()` accepts a `Filter` or a
  `FilterDict`; `register_filter(kind)` extends the dispatcher with
  custom subclasses. `FilterDict` family lives at
  `kaparoo.filesystem.search.filters.types`.
- **Deprecated** — `get_paths`, `get_files`, `get_dirs` (use `search_*`).

### `kaparoo.utils`

- **`timer`** — `Timer` and `LapTimer` context-manager / decorator timers.
- **`optional`** — `replace_if_none`, `factory_if_none`, `unwrap_or_*`.

## 📋 TODO

See [TODO.md](./TODO.md) for tracked open items.

## 📜 Changelog

See [CHANGELOG.md](./CHANGELOG.md) for the version history.

## ⚖️ License

This project is distributed under the terms of the [MIT](./LICENSE) license.

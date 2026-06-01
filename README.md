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

Each submodule ships its own README with focused examples.

### [`kaparoo.filesystem`](https://github.com/kaparoo/kaparoo-python/tree/main/kaparoo/filesystem)

`pathlib`-based filesystem helpers: existence checks (`*_exists`),
`ensure_*` validators, `make_dir(s)` (with a destructive `clean` reset
option), `dir_empty(s)`, `reserve_path(s)` guards for not-yet-existing
destinations, `StagedFile` / `StagedDirectory` for safe (atomic) writes,
path stringification, and a small exception hierarchy.

### [`kaparoo.filesystem.search`](https://github.com/kaparoo/kaparoo-python/tree/main/kaparoo/filesystem/search)

Filesystem traversal with composable filters. Includes `search_paths` /
`search_files` / `search_dirs`, a `Filter` family (pattern, multi-pattern,
logical) that round-trips through JSON-friendly dicts, and an extension
hook for custom filter kinds.

### [`kaparoo.utils`](https://github.com/kaparoo/kaparoo-python/tree/main/kaparoo/utils)

`Timer` / `SegmentTimer` context-manager-and-decorator timers (with
`lap`-split and `measure`-block timings); `Aggregator` for nested,
pluggable metric aggregation (the batch → epoch → run pattern); plus a
small family of helpers for working with `Optional[T]` values
(`replace_if_none`, `unwrap_or_default`, ...).

### [`kaparoo.data`](https://github.com/kaparoo/kaparoo-python/tree/main/kaparoo/data)

Building blocks for dataset code: `DataSequence[T, M]` ABC (item +
metadata), composers (`SlicedSequence`, `ConcatSequence`,
`WindowedSequence`), file-backed templates (`FileFolderSequence`,
`SingleFileSequence`), and `generate_batches`.

## 🎯 Quick example

```python
from kaparoo.filesystem import search_files
from kaparoo.filesystem.search.filters import And, EndsWith, Equals, Not

# All .py files except __init__.py
py_files = search_files(
    "src",
    name_filter=And((EndsWith(".py"), Not(Equals("__init__.py")))),
)
```

See each submodule's README for more.

## 📋 TODO

See [TODO.md](./TODO.md) for tracked open items.

## 📜 Changelog

See [CHANGELOG.md](./CHANGELOG.md) for the version history.

## ⚖️ License

This project is distributed under the terms of the [MIT](./LICENSE) license.

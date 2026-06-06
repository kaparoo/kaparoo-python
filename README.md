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
`search_files` / `search_dirs`, wired to the `kaparoo.filters` DSL via
`part_filter` / `name_filter` / `predicate`, with depth control and a
deprecated `get_*` family.

### [`kaparoo.filesystem.hierarchy`](https://github.com/kaparoo/kaparoo-python/tree/main/kaparoo/filesystem/hierarchy)

A declarative description of a filesystem tree: `File` / `Directory`
nodes whose names are drawn from the `kaparoo.filters` DSL, so one node
can stand for many regularly-named siblings. The `Expandable` filters
(`Literal`, `Template`) also enumerate their names via `expand`. A
representation layer (name-level `matches` / `expand`); the disk
operations it is designed to drive are still to come.

### [`kaparoo.filters`](https://github.com/kaparoo/kaparoo-python/tree/main/kaparoo/filters)

A declarative, composable string-matching DSL: a `Filter` family
(pattern, multi-pattern, logical) that round-trips through JSON-friendly
dicts, plus an extension hook for custom filter kinds. Used by
`kaparoo.filesystem.search` for path matching.

### [`kaparoo.utils`](https://github.com/kaparoo/kaparoo-python/tree/main/kaparoo/utils)

`Timer` / `SpanTimer` context-manager-and-decorator timers (with
`lap`-split and `measure`-block timings); `Aggregator` for nested,
pluggable metric aggregation (the batch → epoch → run pattern;
experimental); plus a small family of helpers for working with
`Optional[T]` values (`replace_if_none`, `unwrap_or_default`, ...).

### [`kaparoo.data`](https://github.com/kaparoo/kaparoo-python/tree/main/kaparoo/data)

Building blocks for dataset code: `DataSequence[T, M]` ABC (item +
metadata), composers (`SlicedSequence`, `ConcatSequence`,
`TransformedSequence`, `WindowedSequence`, `ZippedSequence`), file-backed
templates (`FileFolderSequence`, `FileListSequence`, `SingleFileSequence`),
and `generate_batches`.

## 🎯 Quick example

```python
from kaparoo.filesystem import search_files
from kaparoo.filters import And, EndsWith, Equals, Not

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

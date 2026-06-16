# `kaparoo.filesystem.search`

Filesystem traversal driven by the composable [`kaparoo.filters`](../../filters/)
DSL.

## Entry points

| Function | Yields |
| --- | --- |
| [`search_paths`](./wrappers.py) | files and directories |
| [`search_files`](./wrappers.py) | files only |
| [`search_dirs`](./wrappers.py) | directories only |

All three share the same keyword arguments: `part_filter`, `name_filter`,
`predicate`, `exclude`, `min_depth`, `max_depth`, `ordered`, `stringify`.

```python
from kaparoo.filesystem.search import search_files
from kaparoo.filters import EndsWith

# All .py files anywhere under "src"
search_files("src", name_filter=EndsWith(".py"))
```

## How filters apply

At every visited directory, candidates pass through three gates in
order:

1. **`part_filter`** — matches the directory's path relative to `root`.
   The root itself is matched as `"."`. Directories that fail still get
   descended for further matches. The path is **always forward-slashed**
   (the same normalization `stringify_path` applies), so patterns like
   `Glob("tests/*")` work identically on Windows.
2. **`name_filter`** — matches each entry's leaf name.
3. **`predicate`** — a Python callable receiving the full `Path`, for
   anything beyond what filters express (e.g. `p.stat().st_size > 1024`).

`part_filter` and `name_filter` accept any `Filter` (or a filter dict —
see [`kaparoo.filters`](../../filters/)).

```python
from kaparoo.filesystem.search import search_files
from kaparoo.filters import Glob

# Only collect .py files from the "tests" subtree
search_files(
    ".",
    part_filter=Glob("tests*"),
    name_filter=Glob("*.py"),
    predicate=lambda p: p.stat().st_size > 0,
)
```

## Excluding paths (with pruning)

`exclude` drops paths from the results **and prunes an excluded directory's
whole subtree** — something the filters cannot do (a directory failing
`name_filter` is still descended). It accepts the same excluders as
[`kaparoo.filesystem.hierarchy`](../hierarchy/): a root-relative `StrPath`, a
`Filter` (matched on the root-relative POSIX path), a `Callable` on the
`Path`, or an iterable of these (OR-combined).

```python
from kaparoo.filesystem.search import search_files
from kaparoo.filters import Glob

# skip .git / node_modules entirely -- their subtrees are never walked
search_files("repo", name_filter=Glob("*.py"), exclude=[".git", "node_modules"])
```

`exclude` is applied before the filter gates, so a huge irrelevant subtree
is never visited (unlike a `name_filter`, which would still descend into it).

## Depth control

Depth is 1-based from `root` (its direct children are at depth 1).

```python
# Top-level entries only
search_paths("src", max_depth=1)

# Everything except the top level
search_paths("src", min_depth=2)

# Exactly one level deep
search_paths("src", min_depth=2, max_depth=2)
```

## Filters

The `part_filter` / `name_filter` arguments take the
[`kaparoo.filters`](../../filters/) DSL — pattern, multi-pattern, and
logical filters — and also accept the JSON-friendly dict form directly:

```python
from kaparoo.filesystem.search import search_files

search_files(
    "src",
    name_filter={"kind": "ends_with", "pattern": ".py"},
)
```

## Platform notes

- **Forward-slash paths**: `part_filter` matches against the relative
  directory path normalized via `stringify_path`, so `\\` separators on
  Windows do not leak into your filter patterns. `stringify=True`
  outputs follow the same normalization.
- **Case sensitivity**: filters apply with the case sensitivity set on
  the filter itself (`case_sensitive=True` by default; see
  [`kaparoo.filters`](../../filters/)). The underlying filesystem may
  still be case-insensitive (Windows / macOS defaults), so what
  `Path.walk` *returns* — and therefore what filters see — is the on-disk
  name in its actual case.

## See also

- [`kaparoo.filters`](../../filters/) — the filter DSL applied here
- [`kaparoo.filesystem.hierarchy`](../hierarchy/) — its `conformer` builds a
  `predicate` for these searches
- [`kaparoo.filesystem`](../) — the surrounding filesystem helpers
- [`kaparoo.utils.timer`](../../utils/) for timing filter-heavy walks

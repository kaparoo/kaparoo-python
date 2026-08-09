# `kaparoo.filesystem.search`

Filesystem traversal driven by the composable [`kaparoo.filters`](../../filters/)
DSL.

## Contents

- [Entry points](#entry-points)
- [How filters apply](#how-filters-apply)
- [Excluding paths (with pruning)](#excluding-paths-with-pruning)
- [Descending selectively](#descending-selectively)
- [Depth control](#depth-control)
- [Filters](#filters)
- [Selecting from a collection](#selecting-from-a-collection)
- [Platform notes](#platform-notes)
- [See also](#see-also)

## Entry points

| Function | Yields |
| --- | --- |
| [`search_paths`](./wrappers.py) | files and directories |
| [`search_files`](./wrappers.py) | files only |
| [`search_dirs`](./wrappers.py) | directories only |

All three share the same keyword arguments: `part_filter`, `name_filter`,
`predicate`, `exclude`, `descend`, `min_depth`, `max_depth`, `ordered`,
`stringify`. That set (minus `stringify`, which selects the return type) is
published as `SearchKwargs`, so a wrapper can accept and forward the whole set
as `**options: Unpack[SearchKwargs]` without re-declaring each key.

A wrapper that owns its `predicate`, whether it supplies one internally or
exposes one of a different type over the objects it returns, forwards
`WalkKwargs` instead, which is `SearchKwargs` without `predicate`.
`SearchKwargs` subclasses it, so the two stay in sync:

```python
from typing import Unpack

from kaparoo.filesystem import WalkKwargs, contains, search_dirs

def search_subdirs(root, subpath, **walk: Unpack[WalkKwargs]):
    return search_dirs(root, predicate=contains(subpath), **walk)
```

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

## Descending selectively

`descend` decides whether to walk into a sub-directory, independently of
whether it is returned. A directory that fails `descend` is still offered to
the filters and may be returned, but its subtree is not visited. Unlike
`exclude`, which both drops and prunes, `descend` only prunes.

```python
from kaparoo.filesystem import contains
from kaparoo.filesystem.search import search_dirs

# Return every directory that holds a "Phase" entry, without walking into them.
holds_phase = contains("Phase")
search_dirs("data", predicate=holds_phase, descend=lambda p: not holds_phase(p))
```

`contains(subpath)` is a predicate factory (from `kaparoo.filesystem`) that
tests whether `path / subpath` exists.

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

## Selecting from a collection

`select` is the companion to a walk: given items already in hand (search
results, or anything keyed by a name), it keeps the ones an `include` spec
matches and drops the ones an `exclude` spec matches; on an overlap
`exclude` wins. Each item is named by `key`; both specs are optional and
default to no restriction.

This is the **path-aware** form of
[`kaparoo.filters.select`](../../filters/#selection): the same matching, plus
two filesystem extras the base leaves out: a spec may also be a `.json` /
`.txt` file, and exact-name subpaths are normalized to POSIX `/`.

```python
from kaparoo.filesystem.search import search_dirs, select

# keep only some subtrees, minus a pattern
chosen = select(
    search_dirs("data", max_depth=1),
    key=lambda p: p.name,
    include=["train", "val"],
    exclude={"kind": "glob", "pattern": "*_tmp"},
)
```

Each spec is normalized to one [`kaparoo.filters`](../../filters/) filter and
accepts several forms:

| Form | Example | Meaning |
| --- | --- | --- |
| subpath string | `"train/a"` | one exact name |
| string list | `["train/a", "val/c"]` | those exact names |
| `FilterDict` | `{"kind": "glob", "pattern": "train/*"}` | a pattern |
| mixed list | `["val/c", {"kind": "regex", ...}]` | names **or** patterns |
| `Filter` | `Glob("train/*")` | a filter instance |
| `.txt` file | `"keep.txt"` | one subpath per line (`#` comments, blanks skipped) |
| `.json` file | `"keep.json"` | a `FilterDict` object, or an array |

A bare string is read as a file only when it ends in `.json` / `.txt`;
otherwise it is a single inline subpath. Separators are normalized to POSIX
`/`, and an empty spec (an empty list, or a comment-only listing) places no
restriction, like `None`. The recognized suffixes are exposed as
`SPEC_FILE_SUFFIXES`, and `is_spec_file(source)` reports whether a value would
be read as a file, applying the same case-insensitive suffix test as `select`,
so a leading-dot name like `.json` (which has no suffix) is an inline name, not
a file.

When a spec is an exact-name set (a string, a string list, or a `.txt`
listing), a name matching no item **raises**: a typo says so instead of
silently selecting nothing. An open pattern (`Glob` / `Regex`) is exempt,
since matching nothing may be intended.

Unlike `exclude=` on the search entry points (which prunes a subtree during
the walk), `select` filters an already-materialized collection, so it also
works on items that are not paths.

Need `include` and `exclude` to act separately? `resolve_selector` is the
shared front end: it turns any spec form into one
[`kaparoo.filters`](../../filters/) filter (or `None` for no restriction), so
you can resolve the two and apply them in your own pipeline. The typo check
stays in `select`, not `resolve_selector`.

```python
from kaparoo.filesystem.search import resolve_selector

keep = resolve_selector(cfg["include"])   # a Filter, or None
drop = resolve_selector(cfg["exclude"])
chosen = [x for x in items if (keep is None or keep.matches(name(x)))
          and not (drop is not None and drop.matches(name(x)))]
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

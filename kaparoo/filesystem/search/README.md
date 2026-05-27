# `kaparoo.filesystem.search`

Filesystem traversal with composable, JSON-serializable filters.

## Entry points

| Function | Yields |
| --- | --- |
| [`search_paths`](./wrappers.py) | files and directories |
| [`search_files`](./wrappers.py) | files only |
| [`search_dirs`](./wrappers.py) | directories only |

All three share the same keyword arguments: `part_filter`, `name_filter`,
`predicate`, `min_depth`, `max_depth`, `ordered`, `stringify`.

```python
from kaparoo.filesystem.search import search_files
from kaparoo.filesystem.search.filters import EndsWith

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

```python
from kaparoo.filesystem.search import search_files
from kaparoo.filesystem.search.filters import Equals, Glob

# Only collect .py files from the "tests" subtree
search_files(
    ".",
    part_filter=Glob("tests*"),
    name_filter=Glob("*.py"),
    predicate=lambda p: p.stat().st_size > 0,
)
```

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

## Filter catalog

Concrete classes end in `Filter`; the short TitleCase forms (`Equals`,
`And`, ...) are aliases. All filters are frozen `dataclass`es and
support `==`/`hash`.

### Pattern filters ([`filters/pattern.py`](./filters/pattern.py))

Take a single string `pattern` and a `case_sensitive` flag (default `True`).

| Class / alias | Matches when target ... |
| --- | --- |
| `EqualsFilter` / `Equals` | equals the pattern |
| `StartsWithFilter` / `StartsWith` | starts with the pattern |
| `EndsWithFilter` / `EndsWith` | ends with the pattern |
| `ContainsFilter` / `Contains` | contains the pattern |
| `RegexFilter` / `Regex` | fully matches the regex (via `re.fullmatch`) |
| `GlobFilter` / `Glob` | matches the glob (via `fnmatch.fnmatchcase`) |

```python
from kaparoo.filesystem.search.filters import EndsWith, Glob, Regex

EndsWith(".PY", case_sensitive=False)   # matches "foo.py" and "foo.PY"
Glob("test_?.py")                       # matches "test_1.py", not "test_11.py"
Regex(r"\d{4}-\d{2}-\d{2}\.log")        # matches "2026-01-15.log"
```

### Multi-pattern filters ([`filters/multi_pattern.py`](./filters/multi_pattern.py))

Take a tuple of `patterns`; match when *any* one matches. Duplicates are
deduplicated, first occurrence wins.

| Class / alias |
| --- |
| `EqualsAnyFilter` / `EqualsAny` |
| `StartsWithAnyFilter` / `StartsWithAny` |
| `EndsWithAnyFilter` / `EndsWithAny` |
| `ContainsAnyFilter` / `ContainsAny` |

```python
from kaparoo.filesystem.search.filters import EndsWithAny

EndsWithAny((".png", ".jpg", ".jpeg"))
```

### Logical filters ([`filters/logical.py`](./filters/logical.py))

| Class / alias | Semantics |
| --- | --- |
| `AndFilter` / `And` | all children match |
| `OrFilter` / `Or` | at least one child matches |
| `NotFilter` / `Not` | child does not match |

```python
from kaparoo.filesystem.search.filters import And, EndsWith, Equals, Not

# .py files except __init__.py
And((EndsWith(".py"), Not(Equals("__init__.py"))))
```

## JSON serialization

Every filter round-trips through a `"kind"`-discriminated dict via
`to_dict()` / `Filter.from_dict()`. `Filter.parse()` accepts either an
existing instance or a dict.

```python
import json
from kaparoo.filesystem.search.filters import (
    And, EndsWith, Filter, Not, Equals,
)

f = And((EndsWith(".py"), Not(Equals("__init__.py"))))
spec = json.dumps(f.to_dict())   # store anywhere as JSON
restored = Filter.from_dict(json.loads(spec))
assert restored == f
```

The `search_*` wrappers also accept dicts directly:

```python
from kaparoo.filesystem.search import search_files

search_files(
    "src",
    name_filter={"kind": "ends_with", "pattern": ".py"},
)
```

TypedDicts for static checking live in
[`filters/types.py`](./filters/types.py): `FilterDict` (base; `kind`-only),
`PatternFilterDict`, `MultiPatternFilterDict`, `LogicalChildFilterDict`,
`LogicalChildrenFilterDict`.

## Custom filters

Decorate a `Filter` subclass with `register_filter("<kind>")` to plug
into `Filter.from_dict` / `Filter.parse`.

```python
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from kaparoo.filesystem.search.filters import Filter, register_filter

@register_filter("length_above")
@dataclass(frozen=True)
class LengthAboveFilter(Filter):
    threshold: int

    def matches(self, target: str) -> bool:
        return len(target) > self.threshold

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "length_above", "threshold": self.threshold}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(threshold=data["threshold"])

# Now reachable through the polymorphic dispatcher:
restored = Filter.from_dict({"kind": "length_above", "threshold": 10})
```

## Deprecation: `get_*` -> `search_*`

`get_paths`, `get_files`, and `get_dirs` are kept for backward
compatibility but emit a `DeprecationWarning` and call into the new
search internally. Migration:

| Deprecated | Replacement |
| --- | --- |
| `get_paths(root, recursive=True)` | `search_paths(root)` |
| `get_paths(root, pattern="*.py")` | `search_paths(root, name_filter=Glob("*.py"))` |
| `get_paths(root, excludes=[...])` | `search_paths(root, name_filter=Not(EqualsAny((...))))` |
| `get_paths(root, condition=fn)` | `search_paths(root, predicate=fn)` |
| `get_files(...)` | `search_files(...)` |
| `get_dirs(...)` | `search_dirs(...)` |

## Platform notes

- **Forward-slash paths**: `part_filter` matches against the relative
  directory path normalized via `stringify_path`, so `\\` separators on
  Windows do not leak into your filter patterns. `stringify=True`
  outputs follow the same normalization.
- **Case sensitivity**: filters apply with the case sensitivity set on
  the filter itself (`case_sensitive=True` by default). The underlying
  filesystem may still be case-insensitive (Windows / macOS defaults),
  so what `Path.walk` *returns* — and therefore what filters see — is
  the on-disk name in its actual case.

## See also

- [`kaparoo.filesystem`](../) for the surrounding filesystem helpers
- [`kaparoo.utils.timer`](../../utils/) for timing filter-heavy walks

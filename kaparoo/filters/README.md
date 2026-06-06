# `kaparoo.filters`

A declarative, composable, JSON-serializable string-matching DSL.

Filters test a single string with `matches(target) -> bool` and combine
with boolean logic. They are filesystem-agnostic -- `kaparoo.filesystem.search`
uses them for path matching, but nothing here touches the filesystem.

```python
from kaparoo.filters import And, EndsWith, Equals, Not

# .py files except __init__.py
f = And((EndsWith(".py"), Not(Equals("__init__.py"))))
f.matches("module.py")      # True
f.matches("__init__.py")    # False
```

## Filter catalog

Concrete classes end in `Filter`; the short TitleCase forms (`Equals`,
`And`, ...) are aliases. All filters are frozen `dataclass`es and
support `==` / `hash`.

### Pattern filters ([`pattern.py`](./pattern.py))

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
from kaparoo.filters import EndsWith, Glob, Regex

EndsWith(".PY", case_sensitive=False)   # matches "foo.py" and "foo.PY"
Glob("test_?.py")                       # matches "test_1.py", not "test_11.py"
Regex(r"\d{4}-\d{2}-\d{2}\.log")        # matches "2026-01-15.log"
```

### Multi-pattern filters ([`multi_pattern.py`](./multi_pattern.py))

Take a tuple of `patterns`; match when *any* one matches. Duplicates are
deduplicated, first occurrence wins.

| Class / alias |
| --- |
| `EqualsAnyFilter` / `EqualsAny` |
| `StartsWithAnyFilter` / `StartsWithAny` |
| `EndsWithAnyFilter` / `EndsWithAny` |
| `ContainsAnyFilter` / `ContainsAny` |

```python
from kaparoo.filters import EndsWithAny

EndsWithAny((".png", ".jpg", ".jpeg"))
```

### Logical filters ([`logical.py`](./logical.py))

| Class / alias | Semantics |
| --- | --- |
| `AndFilter` / `And` | all children match |
| `OrFilter` / `Or` | at least one child matches |
| `NotFilter` / `Not` | child does not match |

```python
from kaparoo.filters import And, EndsWith, Equals, Not

# .py files except __init__.py
And((EndsWith(".py"), Not(Equals("__init__.py"))))
```

## JSON serialization

Every filter round-trips through a `"kind"`-discriminated dict via
`to_dict()` / `Filter.from_dict()`. `Filter.parse()` accepts either an
existing instance or a dict.

```python
import json
from kaparoo.filters import And, EndsWith, Equals, Filter, Not

f = And((EndsWith(".py"), Not(Equals("__init__.py"))))
spec = json.dumps(f.to_dict())   # store anywhere as JSON
restored = Filter.from_dict(json.loads(spec))
assert restored == f
```

Consumers such as `search_*` also accept dicts directly:

```python
from kaparoo.filesystem.search import search_files

search_files(
    "src",
    name_filter={"kind": "ends_with", "pattern": ".py"},
)
```

TypedDicts for static checking live in [`types.py`](./types.py):
`FilterDict` (base; `kind`-only), `PatternFilterDict`,
`MultiPatternFilterDict`, `LogicalChildFilterDict`,
`LogicalChildrenFilterDict`.

## Custom filters

Decorate a `Filter` subclass with `register_filter("<kind>")` to plug
into `Filter.from_dict` / `Filter.parse`.

```python
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from kaparoo.filters import Filter, register_filter

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

## Case sensitivity

Pattern and multi-pattern filters take `case_sensitive` (default `True`).
When `False`, matching uses Unicode `str.casefold()`, which is more
aggressive than `str.lower()` (e.g. `"ß".casefold() == "ss"`,
`"ﬁ".casefold() == "fi"`) -- the "caseless linguistic equivalence"
Python recommends. Two names a filesystem treats as distinct may still
match each other under `case_sensitive=False`.

## See also

- [`kaparoo.filesystem.search`](../filesystem/search/) — traversal that
  applies these filters to paths
- [`kaparoo.filesystem`](../filesystem/) — the surrounding filesystem helpers

# `kaparoo.filters`

A declarative, composable, JSON-serializable string-matching DSL.

Filters test a single string with `matches(target) -> bool` and combine
with boolean logic; the [enumerable](#enumerable-filters-enumerablepy)
ones can additionally *list* the finite set of names they match. They are
filesystem-agnostic -- `kaparoo.filesystem.search` uses them for path
matching and `kaparoo.filesystem.hierarchy` for declaring trees, but
nothing here touches the filesystem.

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

### Enumerable filters ([`enumerable.py`](./enumerable.py))

Most filters only *test* a string (`matches`). The enumerable family also
*lists* the concrete strings it stands for, via `expand()` — they
implement the `Expandable` capability. Open-ended filters (`Glob`,
`Regex`, ...) match but cannot enumerate, so they are deliberately not
`Expandable`.

| Class | Matches | `expand()` yields |
| --- | --- | --- |
| `Literal` | the exact name (case-sensitive) | the one name |
| `OneOf` | a name in an explicit set | each name in the set |
| `Template` | a name in the enumerated product | `template.format(*combo)` over the axes |
| `Without` | `base` but not the excluded names | `base`'s names minus the excluded ones |

```python
from kaparoo.filters import Expandable, Glob, Literal, OneOf, Template

list(Literal("data.bin").expand())                  # ['data.bin']
list(OneOf(["train", "val", "test"]).expand())      # ['train', 'val', 'test']
list(Template("shard_{:03d}", range(3)).expand())   # ['shard_000', 'shard_001', 'shard_002']

# Template combines multiple value axes as a cartesian product:
list(Template("{}_{}.png", ["real", "fake"], range(1, 3)).expand())
# ['real_1.png', 'real_2.png', 'fake_1.png', 'fake_2.png']

isinstance(Glob("*.png"), Expandable)               # False — open-ended
isinstance(Literal("data.bin"), Expandable)         # True
```

`Literal` / `OneOf` are the case-sensitive, always-enumerable counterparts
of `Equals` / `EqualsAny` (which can be case-insensitive, and so are not
reliably enumerable). `Template`'s axes are materialized to tuples at
construction; formatting is lazy, so a field-count mismatch surfaces from
`expand()`, not the constructor.

`Without(base, *excluded)` is the enumerable form of
`And(base, Not(...))` — it punches holes in an enumerable set, both
matching and expanding `base` minus anything the `excluded` filters match
(a bare `str` is sugar for `Literal`; an excluded filter may itself be
open-ended, like a `Glob`):

```python
from kaparoo.filters import Glob, Template, Without

list(Without(Template("cam_{:02d}", range(4)), "cam_02").expand())
# ['cam_00', 'cam_01', 'cam_03']
list(Without(Template("img_{:02d}", range(5)), Glob("*_03")).expand())
# ['img_00', 'img_01', 'img_02', 'img_04']
```

All register as ordinary filter kinds (`"literal"` / `"one_of"` /
`"template"` / `"without"`).

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

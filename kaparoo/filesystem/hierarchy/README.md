# `kaparoo.filesystem.hierarchy`

A declarative, composable description of a filesystem tree — directories
and files as immutable objects, with names drawn from the
[`kaparoo.filters`](../../filters/) DSL so a single node can stand for a
run of regularly-named siblings.

> **Scope.** Today this package is the *representation* plus name-level
> semantics (filter `matches` and, where applicable, `expand`). The
> disk-touching operations it is designed to drive — scaffolding a tree,
> validating an existing tree, matching a path against a tree — are not
> implemented yet.

## Nodes

Build a tree from two node types. As name sugar, a bare `str` becomes a
`Literal` and a `list[str]` becomes a `OneOf` (one node standing for
several literally-named siblings that share a structure). A directory's
`children` accepts any iterable (frozen to a tuple, order preserved).

| Class | Role |
| --- | --- |
| [`File`](./nodes.py) | a leaf entry |
| [`Directory`](./nodes.py) | an entry holding ordered `children` |
| [`Entry`](./nodes.py) | abstract base of both (carries `name`) |

```python
from kaparoo.filesystem.hierarchy import Directory, File, Template
from kaparoo.filters import Glob

dataset = Directory("dataset", [
    File("metadata.json"),                              # literal file
    Directory("images", [
        File(Glob("*.png")),                            # many image files
    ]),
    Directory(Template("shard_{:03d}", range(8)), [     # shard_000 .. shard_007
        File("data.bin"),                               # shared by every shard
    ]),
])
```

A patterned directory's `children` describe the shape shared by *every*
sibling its name matches.

## Names are filters

A node's `name` is any [`kaparoo.filters.Filter`](../../filters/), so the
full filter DSL describes which siblings a node matches:

```python
from kaparoo.filesystem.hierarchy import Directory, File
from kaparoo.filters import EndsWithAny, Regex

Directory(Regex(r"v\d+"), [...])            # v0, v1, v2, ...
File(EndsWithAny((".png", ".jpg")))         # any image file
```

`hierarchy` depends on `kaparoo.filters`, never the reverse — and on
nothing in `kaparoo.filesystem.search`.

## Depth: descendants at unknown levels

By default a child sits one level below its parent (`depth=1`). Set
`depth` to place an entry deeper, past intermediate directories whose
names you do not know. It is an inclusive `(min, max)` range, exposed as
the `min_depth` / `max_depth` properties:

| `depth=` | meaning | `(min_depth, max_depth)` |
| --- | --- | --- |
| `1` (default) | direct child | `(1, 1)` |
| `N` | exactly `N` levels below | `(N, N)` |
| `None` | any depth, one or more levels — the tree-level `**` | `(1, None)` |
| `(min, max)` | an inclusive range (`max=None` is unbounded) | `(min, max)` |

```python
from kaparoo.filesystem.hierarchy import Directory, File
from kaparoo.filters import Glob

Directory("dataset", [
    Directory("frames", [File(Glob("*.png"))], depth=2),  # dataset/<any>/frames/*.png
    Directory("checkpoints", depth=(1, 3)),               # 1 to 3 levels below
    File("config.yaml", depth=None),                      # config.yaml anywhere below
])
```

`depth` is part of a node's value identity (`Directory("x", depth=None)
!= Directory("x")`; `depth=3` and `depth=(3, 3)` are equal) and `repr`
shows it only when non-default, in its most compact form. Because the
intermediate names are unknown, any depth beyond `1` describes structure
for *matching*, not scaffolding — and like the rest of the
representation, the matching that consumes the depth range is not
implemented yet.

## Enumeration: `Expandable`

A plain filter only *tests* a name (`matches`). Two filters defined here
also *enumerate* the names they stand for, via `expand` — they implement
the `Expandable` capability, which is what scaffolding will require.

| Class | `matches` | `expand` |
| --- | --- | --- |
| [`Literal`](./patterns.py) | name equals the value | the one name |
| [`OneOf`](./patterns.py) | name is one of an explicit set | each name in the set |
| [`Template`](./patterns.py) | name is in the enumerated set | `template.format(value)` per value |

```python
from kaparoo.filesystem.hierarchy import Expandable, Literal, OneOf, Template
from kaparoo.filters import Glob

list(Template("shard_{:03d}", range(3)).expand())  # ['shard_000', 'shard_001', 'shard_002']
list(OneOf(["train", "val", "test"]).expand())     # ['train', 'val', 'test']
list(Literal("data.bin").expand())                 # ['data.bin']

isinstance(Glob("*.png"), Expandable)              # False — open-ended, cannot scaffold
isinstance(Literal("data.bin"), Expandable)        # True
```

One node can stand for several literally-named siblings that share a
structure — `list[str]` sugar makes this concise:

```python
from kaparoo.filesystem.hierarchy import Directory, File
from kaparoo.filters import Glob

# both `train/` and `val/` get the same layout
Directory(["train", "val"], [
    Directory("images", [File(Glob("*.png"))]),
    File("labels.json"),
])
```

`Template` materializes `values` to a tuple at construction and applies a
single positional `str.format` field; formatting is lazy, so a template
that cannot accept a value raises from `expand`, not at construction.

Because `Literal` and `Template` are `Filter`s, they participate in the
filter registry and round-trip through `to_dict` / `Filter.from_dict`
like any other filter (kinds `"literal"` and `"template"`).

## Value semantics

Patterns and nodes are immutable value objects: equal by type and fields,
hashable, with a `repr` that round-trips the fields.

```python
from kaparoo.filesystem.hierarchy import File, Literal

File("a.txt") == File(Literal("a.txt"))   # True (str is sugar for Literal)
repr(File("a.txt"))                        # "File(Literal(name='a.txt'))"
{File("a"), File("a")}                      # one element
```

## See also

- [`kaparoo.filters`](../../filters/) — the filter DSL node names are
  drawn from
- [`kaparoo.filesystem.search`](../search/) — the traversal layer that
  also builds on `kaparoo.filters`
- [`kaparoo.filesystem`](../) — the surrounding filesystem helpers

# `kaparoo.filesystem.hierarchy`

A declarative, composable description of a filesystem tree — directories
and files as immutable objects, with names drawn from the
[`kaparoo.filters`](../../filters/) DSL so a single node can stand for a
run of regularly-named siblings.

> **Scope.** Today this package is the *representation* plus name-level
> semantics (filter `matches` and, where applicable, `expand`) and the
> first disk-touching operation, [`match`](#matching-match). The remaining
> operations it is designed to drive — validating an existing tree,
> scaffolding a new one — are not implemented yet.

## Nodes

Build a tree from two node types. As name sugar, a bare `str` becomes a
`Literal` and a `list[str]` becomes a `OneOf` (one node standing for
several literally-named siblings that share a structure). A directory's
`children` accepts any iterable (frozen to a tuple, order preserved).

| Class | Role |
| --- | --- |
| [`File`](./entry.py) | a leaf entry |
| [`Directory`](./entry.py) | an entry holding ordered `children` (any `Node`s) |
| [`Entry`](./entry.py) | abstract base of `File` / `Directory` (carries `name`) |
| [`Exclusive`](./group.py) | a mutual-exclusion constraint among siblings |
| [`Together`](./group.py) | a co-occurrence (all-or-nothing) constraint among siblings |
| [`Group`](./group.py) | abstract base of the constraint nodes (`Exclusive`, `Together`) |
| [`Node`](./base.py) | abstract base of everything in `children` (`Entry` or `Group`) |

```python
from kaparoo.filesystem.hierarchy import Directory, File
from kaparoo.filters import Glob, Template

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
for *matching* (which [`match`](#matching-match) honors), not for
scaffolding.

## Presence: `required`

Each entry takes a keyword-only `required` flag (default `False`) asserting
that it must be present — `File("metadata.json", required=True)`. By
default the spec describes structure (what *may* be there); `required=True`
adds a "must be there" assertion that a validator enforces. (Attribute
conditions — size, emptiness, ... — are a separate, planned feature; see
`TODO.md`.)

## Mutual exclusion: `Exclusive`

Some siblings must not coexist — `setup.py` vs `pyproject.toml`,
`README.md` vs `README.rst`, `build/` vs `dist/`. An `Exclusive` placed in
a directory's `children` declares that **at most one** of its alternatives
may exist:

```python
from kaparoo.filesystem.hierarchy import Directory, Exclusive, File

Directory("project", [
    File("README.md"),
    Exclusive(File("setup.py"), File("pyproject.toml")),   # at most one
])
```

Each alternative is a set of one or more entries on the same side of the
exclusion, so the constraint partitions siblings into sides:

```python
Exclusive(
    [File("setup.py"), File("setup.cfg")],   # the legacy build files ...
    File("pyproject.toml"),                   # ... or the modern one
)
```

Within an alternative the nodes are **independent** — `setup.py` and
`setup.cfg` may appear together or singly; they just can't appear
alongside `pyproject.toml`. For "all or nothing" co-occurrence, use
`Together`. `required=True` tightens "at most one alternative" to "at
least one". `Exclusive` is a `Node` but not an `Entry` — it has no name of
its own — so a directory's `children` hold `Node`s. The validation that
enforces it is not implemented yet.

Alternatives (and `Together` members) are `Node`s, so constraints **nest**
— an alternative may itself be a group:

```python
Exclusive(Together(File("a"), File("b")), File("c"))   # {a and b together} or c
```

## Co-occurrence: `Together`

Some siblings are meaningless apart and must come as a set — a sharded
file and its index, a certificate and its key. A `Together` declares its
members **all-or-nothing**: every one exists, or none does.

```python
from kaparoo.filesystem.hierarchy import Directory, File, Together

Directory("model", [
    Together(File("weights.bin"), File("weights.index")),   # both or neither
])
```

`required=True` tightens "all or nothing" to "all present". `Together` is
the dual of `Exclusive`; the two compose by sitting side by side in
`children` — an `Exclusive` between sides, plus a `Together` that makes
one side co-occur. Like the rest of the representation, the validation
that enforces it is not implemented yet.

Both constraints share a `Group` base that carries `required` and an
`entries` property — the **leaf** entries the constraint references,
descending recursively through any nested groups — so a tree walk reaches
every concrete entry uniformly, whatever the constraint's shape:

```python
Exclusive([File("a"), File("b")], File("c")).entries          # (File("a"), File("b"), File("c"))
Exclusive(Together(File("a"), File("b")), File("c")).entries  # (File("a"), File("b"), File("c"))
```

The structured view (`alternatives` / `members`) keeps the nesting;
`entries` flattens it to the leaves.

## Enumerable names

A node's name can be any filter, but **scaffolding** (creating the tree
on disk) needs names it can *list*, not just *match*. Those are the
`Expandable` filters from [`kaparoo.filters`](../../filters/) — `Literal`,
`OneOf`, and `Template`. Open-ended filters (`Glob`, `Regex`, ...) match
but cannot enumerate, so they describe structure for matching only.

```python
from kaparoo.filters import Expandable, Glob, Literal

isinstance(Literal("data.bin"), Expandable)   # True  — one concrete name
isinstance(Glob("*.png"), Expandable)         # False — open-ended
```

One node can stand for several literally-named siblings that share a
structure — `str` / `list[str]` name sugar makes this concise:

```python
from kaparoo.filesystem.hierarchy import Directory, File
from kaparoo.filters import Glob

# both `train/` and `val/` get the same layout
Directory(["train", "val"], [
    Directory("images", [File(Glob("*.png"))]),
    File("labels.json"),
])
```

## Value semantics

Patterns and nodes are immutable value objects: equal by type and fields,
hashable, with a `repr` that round-trips the fields.

```python
from kaparoo.filesystem.hierarchy import File
from kaparoo.filters import Literal

File("a.txt") == File(Literal("a.txt"))   # True (str is sugar for Literal)
repr(File("a.txt"))                        # "File(Literal(name='a.txt'))"
{File("a"), File("a")}                      # one element
```

## Serialization

A whole tree round-trips through a `"node"`-discriminated dict via
`to_dict()` / `Node.from_dict()`, recursing into child nodes and (for
entries) the filter `name` — so a spec can be stored as JSON. Defaults
(`depth=(1, 1)`, `required=False`, empty `children`) are omitted.

```python
import json
from kaparoo.filesystem.hierarchy import Directory, File, Node
from kaparoo.filters import Glob

tree = Directory("dataset", [
    File("metadata.json"),
    Directory("images", [File(Glob("*.png"))]),
])
blob = json.dumps(tree.to_dict())
assert Node.from_dict(json.loads(blob)) == tree
```

A round-trip preserves value equality, not object identity: a reused
subtree comes back as distinct-but-equal nodes (JSON has no aliasing).

## Matching: `match`

`match(tree, root)` maps each path under `root` to the spec node(s) it
corresponds to — by name (the node's filter), type (`File` ↔ file,
`Directory` ↔ directory), and `depth` (intermediate levels of unknown name
are skipped). `root` is the *container*, like `search`'s root; a path
matching several nodes yields one pair per node.

```python
from kaparoo.filesystem.hierarchy import Directory, File, match
from kaparoo.filters import Glob

spec = Directory("dataset", [
    File("metadata.json"),
    Directory("images", [File(Glob("*.png"))]),
])
for path, node in match(spec, "/data"):   # "/data" contains "dataset"
    ...   # path -> the spec node it matches
```

`match` reports only what is *present* — a `Group` is treated as "any of
its entries may appear," so it does not enforce `Exclusive` / `Together`,
and it does not report missing `required` entries. Those are the job of
`validate`, which is still to come (and will build on `match`).

## See also

- [`kaparoo.filters`](../../filters/) — the filter DSL node names are
  drawn from
- [`kaparoo.filesystem.search`](../search/) — the traversal layer that
  also builds on `kaparoo.filters`
- [`kaparoo.filesystem`](../) — the surrounding filesystem helpers

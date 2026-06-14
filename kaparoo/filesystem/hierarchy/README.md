# `kaparoo.filesystem.hierarchy`

A declarative, composable description of a filesystem tree — directories
and files as immutable objects, with names drawn from the
[`kaparoo.filters`](../../filters/) DSL so a single node can stand for a
run of regularly-named siblings.

> **Scope.** This package is the *representation* plus name-level semantics
> (filter `matches` and, where applicable, `expand`) and the disk
> operations [`match`](#matching-match),
> [`validate`](#validation-validate), [`conforms`](#filtering-paths-conforms)
> (read), and [`scaffold`](#scaffolding-scaffold) (write).

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
adds a "must be there" assertion, and [`validate`](#validation-validate)
reports a `missing` entry **only** for `required` ones. The default is
deliberately opt-in: a pattern entry like `File(Glob("*.png"))` naturally
means "zero or more", so describing a layout never *requires* anything
until you say so. For an "everything listed must exist" layout, mark each
entry `required=True`.

## Attribute conditions: `condition=`

Beyond name, type, and presence, an entry can assert a `condition` on the
matched path's filesystem attributes — a serializable `Condition` from
[`conditions.py`](./conditions.py):

```python
from kaparoo.filesystem.hierarchy import Directory, File
from kaparoo.filesystem.hierarchy.conditions import (
    And, ChildCount, Content, NonEmpty, Size,
)

File("model.bin", condition=Size(min=1))                # at least one byte
File("cache.tmp", condition=Size(max=0))                # an empty file
Directory("data", condition=NonEmpty())                 # a non-empty directory
Directory("shards", condition=ChildCount(min=8))        # 8+ entries
File("a", condition=And((Size(min=1), Size(max=1000))))  # And / Or / Not compose
```

Conditions are a **validation** concern: `match` still maps paths by name /
type / depth alone, while `validate` checks each matched path's `condition`
and lists the failures in `report.failed` (`report.ok` requires it empty);
`conforms` likewise requires the top node's `condition` to hold. The
metadata conditions (`Size`, `ChildCount`, `Empty` / `NonEmpty`) are
declarative and round-trip through `to_dict` / `from_dict`.

For arbitrary file **content** checks — which a callable cannot serialize —
`Content("name")` stores only a serializable reference; the callable is
supplied at validation time, so the spec stays serializable and
value-comparable:

```python
report = validate(spec, root, checks={"valid_schema": lambda p: ...})
```

The callable receives the matched **absolute path** — a live `pathlib.Path`,
not just a name — so it is free to navigate to siblings and ancestors with
`.parent`, `iterdir()`, `glob(...)`, etc. A condition can therefore relate
its node to others at the same or a higher level. For example, "this file's
line count equals the number of files in a sibling folder":

```python
def lines_match_sibling_count(path: Path) -> bool:
    lines = len(path.read_text().splitlines())
    return lines == sum(1 for _ in (path.parent / "other").iterdir())

validate(spec, root, checks={"lines_match": lines_match_sibling_count})
```

The path is the only argument — navigation is relative to the matched path,
not to `root` — so anchor cross-references off `path.parent`.

When a `Content` name is absent from `checks`, `on_missing` decides:
`"error"` (the default) raises, `"skip"` treats it as satisfied.

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
its own — so a directory's `children` hold `Node`s.
[`validate`](#validation-validate) enforces it.

Alternatives (and `Together` members) are `Node`s, so constraints **nest**
— an alternative may itself be a group:

```python
Exclusive(Together(File("a"), File("b")), File("c"))   # {a and b together} or c
```

### Resolving conflicts by priority: `on_conflict`

By default, several alternatives present at once is a `violation`
(`on_conflict="error"`). Set `on_conflict="priority"` to instead *resolve*
the ambiguity by **declaration order** — the first present alternative
wins, and the lower-priority present ones are reported as `unexpected`
(their files no longer belong to the resolved tree). Reorder the
alternatives to change the priority:

```python
Exclusive(
    File("pyproject.toml"),   # preferred when both exist ...
    File("setup.py"),         # ... this one becomes `unexpected`
    on_conflict="priority",
)
```

`on_conflict` is part of the spec, so it serializes and the same priority
also drives [`scaffold`](#scaffolding-scaffold), which creates the first
alternative (a resolved `Exclusive` has a single, deterministic choice).

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
one side co-occur. [`validate`](#validation-validate) enforces it.

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

A node's name can be any filter, but [**scaffolding**](#scaffolding-scaffold)
(creating the tree on disk) needs names it can *list*, not just *match*.
Those are the `Expandable` filters from [`kaparoo.filters`](../../filters/) —
`Literal`, `OneOf`, `Template`, and `Without`. Open-ended filters (`Glob`,
`Regex`, ...) match but cannot enumerate, so they describe structure for
matching only.

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

## Custom nodes

`register_node("<kind>")` plugs a `Node` subclass into the
`"node"`-discriminated `Node.from_dict` dispatcher, the same way
`register_filter` extends the filter DSL.

**Subclass `Entry` or `Group`, never `Node` directly.** `match` and
`validate` rely on the closed `Entry | Group` world: any node that is not
a `Group` is treated as an `Entry`. A third `Node` subtree makes those
casts unsound, so a custom kind must extend one of the two known subtrees
and satisfy its contract — an `Entry` supplies `_fields`, `to_dict`, and
`from_dict`; a `Group` supplies `entries`, `to_dict`, and `from_dict`.

```python
from collections.abc import Mapping
from typing import Any, Self

from kaparoo.filesystem.hierarchy import Entry, register_node
from kaparoo.filters import Filter

@register_node("symlink")
class Symlink(Entry):
    """A named symbolic-link entry."""

    __slots__ = ()

    def _fields(self) -> tuple[object, ...]:
        return (self._name,)

    def to_dict(self) -> dict[str, Any]:
        return {"node": "symlink", "name": self._name.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(Filter.from_dict(data["name"]))
```

This minimal entry serializes only its `name`; to also carry `depth` /
`required` / `condition`, merge `self._common_payload()` into `to_dict`
and read them back in `from_dict`. Most specs need only the built-in
nodes — custom kinds are an advanced extension point.

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

A path may match several nodes at once (overlapping filters). By default
`match` yields one pair per node and stays fully lazy; the variants let you
shape that:

```python
from kaparoo.filesystem.hierarchy import match, match_map

match(spec, "/data")                  # (path, node) per match — duplicates kept, lazy
match(spec, "/data", unique=True)     # same, but identical (path, node) pairs suppressed
match_map(spec, "/data")              # {path: (node, ...)} — overlapping nodes grouped
match_map(spec, "/data").items()      # iterate (path, nodes) tuples instead
```

`match` streams; `match_map` materializes the full mapping before
returning (its nodes are distinct, in spec-traversal order).

`exclude=` drops specific paths from the results — e.g. punching holes in a
nested `Template` product, which the name-level `Without` cannot do because
the axes live at different tree levels. An excluder (or an iterable of
them, OR-combined) is a concrete **root-relative** `StrPath`, or a callable
taking the **root-relative** `Path`; a dropped directory has its whole
subtree pruned:

```python
match(spec, "/data", exclude=["cam_01/frame_0003.png"])     # drop one cell
match(spec, "/data", exclude=lambda p: p.suffix == ".tmp")  # drop by rule
match(spec, "/data", exclude=["scratch", "cam_02/frame_0010.png"])  # branch + cell
```

`match` reports only what is *present* — a `Group` is treated as "any of
its entries may appear," so it does not enforce `Exclusive` / `Together`,
and it does not report missing `required` entries. Those are the job of
`validate`.

## Validation: `validate`

`validate(tree, root)` checks a real directory against the spec and returns
a `ValidationReport`:

```python
from kaparoo.filesystem.hierarchy import Directory, Exclusive, File, validate

spec = Directory("project", [
    File("README.md", required=True),
    Exclusive(File("setup.py"), File("pyproject.toml")),
])
report = validate(spec, "/repo")   # "/repo" contains "project"
if not report:                     # truthy only when fully conformant
    print(report.missing, report.unexpected, report.violations)
```

| Field | Meaning |
| --- | --- |
| `matched` | `{path: (node, ...)}`, exactly `match_map` |
| `unexpected` | paths matching no node (see below) |
| `missing` | a `required` entry, or a `required` `Exclusive` / `Together` with nothing present |
| `violations` | `Exclusive` with more than one side present (unless `on_conflict="priority"` resolves it — losers fall to `unexpected` instead), or `Together` only partly present |
| `failed` | `(path, node)` pairs where the matched path broke the node's attribute [`condition`](#attribute-conditions-condition) |
| `ok` | `True` (and the report is truthy) when the four above are empty |

A path is **unexpected** unless it is matched or an ancestor of a match —
so anything below an *unspecified* directory counts too (describe the
contents, or accept them with a wildcard like `File(Glob("*"))`, to keep
them out of the report). A `required` entry is satisfied once its name
matches one present path — for an enumerable name (`OneOf` / `Template`)
that means *at least one* of the listed names exists, not all. `validate`
also takes the same
`exclude=` as `match`; excluded paths are dropped from `matched` and are not
reported `unexpected`.

## Filtering paths: `conforms`

`conforms(spec)` builds a path predicate (a `search` predicate) that
accepts a path when it realizes `spec`'s **top** node:

```python
from kaparoo.filesystem.search import search_dirs
from kaparoo.filesystem.hierarchy import Directory, File, conforms
from kaparoo.filters import Glob

spec = Directory("dataset", [
    File("metadata.json"),
    Directory("images", [File(Glob("*.png"))]),
])
keep = conforms(spec)
# keep the subdirectories that are themselves a conforming `dataset`
search_dirs("/data", predicate=keep)
```

A path realizes the top node when it is a **file** matching a top `File`'s
name, or a **directory** matching a top `Directory`'s name *whose subtree
conforms* (via `validate`); a top `Group` is realized by any one of its
alternatives / members. The path is always tested as the *top* of `spec`,
never against an inner node — `conforms(Directory("dataset", [...]))`
accepts a conforming `dataset/` directory, not the files inside it. A
`condition` on the top node is enforced too: a top `File` / `Directory`
carrying a `Size`, `ChildCount`, `Content`, … condition realizes the spec
only when that condition also holds. (Checking whether a concrete path or
sub-spec is *contained* anywhere within a spec is a separate, future
capability.)

## Scaffolding: `scaffold`

`scaffold(tree, root)` is the **write** counterpart of `match` / `validate`:
it creates on disk the structure the spec describes, under `root` (the
container, created if absent), and returns the newly created paths:

```python
from kaparoo.filesystem.hierarchy import Directory, Exclusive, File, scaffold
from kaparoo.filters import Glob, Template

spec = Directory("project", [
    File("README.md"),
    Directory(["train", "val"], [File("data.csv")]),     # both subtrees
    File(Template("shard_{:02d}.bin", range(4))),         # shard_00 … shard_03
    Exclusive(File("pyproject.toml"), File("setup.py")),  # the first one
    File(Glob("*.log")),                                  # open → skipped
])
scaffold(spec, "/tmp/out")          # creates the tree, returns new paths
scaffold(spec, "/tmp/out", dry_run=True)   # preview only, touches nothing
```

Only **enumerable** nodes are materialized: a node is creatable when its
name is an `Expandable` filter (`Literal` / `OneOf` / `Template` / `Without`,
and the `str` / `list[str]` sugar) **and** it sits at a fixed `depth` of 1.
Open names (`Glob`, `Regex`) and non-fixed depths are *acceptance patterns*,
not generators — they are **skipped** when optional, but a `required` one
cannot be satisfied and raises. `Together` creates all its members
(all-or-nothing — a non-creatable member skips the whole set unless
`required`); `Exclusive` creates the **first fully-creatable alternative**
(declaration order is the priority, the same rule as
[`on_conflict`](#resolving-conflicts-by-priority-on_conflict)).

Files are created **empty** (the skeleton, not its contents). Creation is
**idempotent**: an existing directory is descended unchanged and an existing
file is never clobbered, so only newly created paths are returned and a
re-run is a no-op. A path that exists with the wrong kind (a file where a
directory is described, or vice versa) is a conflict and raises. `dry_run`
runs every check but no write, returning the paths that *would* be created.

## See also

- [`kaparoo.filters`](../../filters/) — the filter DSL node names are
  drawn from
- [`kaparoo.filesystem.search`](../search/) — the traversal layer that
  also builds on `kaparoo.filters`
- [`kaparoo.filesystem`](../) — the surrounding filesystem helpers

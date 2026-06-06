# TODO

Tracked items that are not yet captured in code or tests, organized by
module. Promote an item to a CHANGELOG entry once it lands.

---

## 🧮 `kaparoo.utils.aggregate`

### `Stored` reduction (deferred — add when concrete need arises)

Non-decomposable statistics (median, quantiles) that require storing every
`(value, weight)` pair. O(n) memory — documented escape hatch from the
online monoid contract.

```python
@dataclass(frozen=True)
class Stored(Reduction[list[tuple[float, float]]]):
    reduce: Callable[[Sequence[float], Sequence[float]], float]
```

Convenience wrappers built on top: `Median()`, `Quantile(q)`.

**Blocker before shipping**: `state()` docstring claims states are immutable;
`Stored.step` would mutate a list. Resolve by relaxing the docstring or
returning a new list in `step`.

### Remove `experimental` tag

Once the reduction family is complete (after `Stored` is merged or explicitly
decided against), remove the `experimental` note from the module docstring,
class docstrings, CHANGELOG entry, and `kaparoo/utils/README.md`.

### `Aggregator.weight` semantics with heterogeneous updates

`weight` accumulates across all `update` calls regardless of which metric
keys were present. Ambiguous when updates have varying key sets. Document
explicitly or add per-metric weight tracking if a concrete case demands it.

### `Aggregator` single-dict refactor (perf)

`_reductions` and `_states` are parallel dicts keyed identically, so every
`update` / `compute` / `state` / `merge` does two keyed lookups per metric.
Collapse them into one `dict[str, tuple[Reduction, state]]`: `update` then
reads the pair once per metric (via a `_MISSING` sentinel — a `None` state
is valid for `Min` / `Max` / `Last`, so `.get() is None` cannot
disambiguate), and `merge` iterates the other aggregator's internals
directly instead of allocating a full `state()` snapshot. Per-sample hot
path; behavior-preserving (tuples keep `state()`'s immutable-snapshot
contract).

---

## 🌳 `kaparoo.filesystem.hierarchy`

### Scaffolder (the remaining spec operation)

`match` / `match_map` (`match.py`), `validate`, and `conforms`
(`validate.py`) have landed: `match` maps each on-disk path to its spec
node(s) honoring `depth` and descending through `Group`s; `validate`
returns a conformance report (`matched` / `unexpected` / `missing` /
`violations`); `conforms(spec)` builds a `search` predicate accepting a
path that realizes *any* entry in the spec (file by name, directory by name
+ conforming subtree). Settled policies: `required`-enumerable is **"at
least one present"**; `unexpected` is **"not matched and not an ancestor of
a match"**; `conforms` matches **any node** in the spec, not just the top.
The operation still to write — a free function, nodes as pure value
objects, reusing `search`'s traversal and `stringify_path` where helpful:

- `scaffold(tree, root)` — write op: create the tree from `Expandable`
  names (and `required`).

`match` does not replace `search`: `search` *discovers* paths matching
stateless filters; `match` *checks / maps* a real tree against a known
structural spec (depth, constraints, presence). They share `kaparoo.filters`
and may share traversal, but answer different questions.

### `match` path exclusion (`exclude=`) — next up

Generalize the original "cross-level cell exclusion" (drop e.g.
`cam_01/frame_0003.png` from a nested `Template` × `Template` product) into
a general path-reject. It lives on the **operation**, not the
representation: `match` / `match_map` gain an `exclude=` keyword.

```python
match(tree, root, *, unique=False, exclude=None)
match_map(tree, root, *, exclude=None)
```

`exclude` accepts an *excluder* or an iterable of mixed excluders
(OR-combined). Each excluder denotes a set of paths to drop and normalizes
to a single path-predicate `(relpath) -> bool` (relative to `root`):

| Excluder | Normalization |
| --- | --- |
| `StrPath` | membership in a set of root-relative posix paths (concrete cells) |
| `Node` | a sub-spec (possibly a whole tree); exclude the paths matched by its **terminal nodes** — see below — declarative + serializable |
| `Callable[[Path], bool]` | used as-is (escape hatch, like `search`'s `predicate`) |

Accepted scope is **`StrPath | Node | Callable`** (single or iterable).
Deliberately **not** a bare `Filter`: `Glob("*.tmp")` alone is ambiguous
(match the *name* or the whole *relative path*? which type? what depth?).
Wrap it in a node instead — `File(Glob("*.tmp"), depth=None)` — which fixes
name, type, and depth unambiguously. (Revisit if a concrete need for a bare
`Filter` arises; would have to pin name-vs-path semantics first.)

A `Node` excluder may be a multi-level tree. To make that intuitive,
exclude only the paths matched by the excluder's **terminal** nodes -- a
`File`, or a `Directory` with no `children`. A `Directory` that *has*
children is only an *addressing* path: it is not itself excluded or pruned,
its children select what to drop. Combined with the directory-pruning rule
below, one mechanism then covers every case:

| Excluder | Effect |
| --- | --- |
| `Directory("build")` (no children) | drop `build` and **prune its whole subtree** (a branch) |
| `Directory("logs", [File(Glob("*.tmp"))])` | drop only `logs/*.tmp`; keep `logs` and the rest |
| `File(Glob("*.tmp"), depth=None)` | drop every `.tmp` file at any depth |
| a deeper tree | drop the leaf cells it addresses, not the containers |

Semantics:

- A matched excluder path is dropped from the results; if it is a
  **directory, its whole subtree is pruned** (not descended) — so a
  childless `Directory` excluder removes a whole branch, while a `File`
  excluder removes just that path.
- Guard the single-`str`/`PathLike` case (a bare `str` is iterable) by
  wrapping a lone excluder into a one-element list.

Implementation:

- A normalizer turns each excluder into a `(relpath) -> bool`; `StrPath`
  builds a set, `Callable` passes through, and a `Node` runs one extra
  `match` pass up front filtered to terminal nodes —
  `{p for p, n in match(node, root) if _is_terminal(n)}` where
  `_is_terminal` is a `File` or a childless `Directory`. Combine with
  `any(...)`.
- Thread the combined predicate into the `_walk_depths` `Path.walk` loop
  (consumed by `_match_children`): one check site skips excluded entries
  and `dirnames`-prunes excluded directories, so exclusion stays consistent
  across overlap, `depth` ranges, `unique`, and `match_map`. The core
  matching logic is untouched.

### Attribute conditions on `File` / `Directory`

Beyond the name filter and the `required` presence flag, an entry may need
*attribute* conditions on the actual filesystem object — file size,
emptiness, extension, mtime; directory child count, etc. (needed for both
files and directories).

Must stay **declarative and serializable** (the representation round-trips
through `to_dict` / `from_dict`), so this is a small condition DSL over
metadata, not an arbitrary Python callable (a lambda cannot be serialized
or value-compared). Design alongside the matcher / validator, which is
what consumes such conditions.

### `required` default

The presence flag defaults to `False` (opt-in). When the validator lands,
reconsider whether a strict "listed = required" default, or a
`validate(require_all=...)` mode, reads better.

### Possible path-name sugar

Node-name sugar (`File("x")`, `Directory(["a", "b"])`) names a *single*
path component; a separator (`/` or `\`) is rejected with `ValueError`.

A separate convenience could let a separator-containing name expand to
nested nodes — e.g. `Directory("a/b/c", children)` becoming
`Directory("a", [Directory("b", [Directory("c", children)])])`, and
`File("a/b.txt")` the file `b.txt` two levels down.

Deferred because it overloads the `str` sugar (a name string would
sometimes mean one `Literal`, sometimes a whole subtree) and interacts
awkwardly with `depth` (which level would `depth` apply to?). Add as an
explicit, separate feature if a concrete need arises.

### Operation throughput (perf — deferred)

From the codebase-wide perf review; the higher-value wins already landed
(the single-walk `_match_children` rewrite, filter set-membership
precompute, search `stringify_path` guard). Remaining:

- **`validate` walks the disk twice** — once via `match_map` (spec-driven)
  and once in `_unexpected` (disk-driven). It is a constant 2× factor, not
  an algorithmic blow-up; collapsing it needs a disk-driven pass that
  classifies matched vs unexpected in a single walk. Defer until profiling
  shows it matters.
- **`conforms(spec)` re-validates per candidate** — used as a `search`
  predicate over many directories, it re-walks each candidate's subtree
  (O(paths × subtree)). Inherent to the per-path "is this a conforming
  instance?" semantics; documented cost, not easily removable.

---

## 🗂️ `kaparoo.filesystem`

### `make_dir` / `make_dirs` redundant `is_dir()` stat (perf — marginal)

`_ensure_directory_target` already establishes whether the path is a
directory, then the caller re-stats `path.is_dir()` for the `clean` branch.
The redundancy fires **only** in the `clean=True` + existing-directory case
(a rare, destructive path). A naive precompute would *regress* the common
create-new path, where short-circuit evaluation currently skips `is_dir`
entirely — so a correct fix must read `exists` once, compute `is_dir` only
when it exists, and return it for the caller to reuse. Low value; do only
if directory-creation throughput is ever shown to matter.

---

## 🧱 `kaparoo.data.sequences`

### Batch-delegating `get_items` on composers (perf)

`SlicedSequence`, `TransformedSequence`, `WindowedSequence`, and
`ConcatSequence` do not override `get_items` / `get_metas`, so the base
loops `get_item` per element (re-resolving each index). Slicing a composed
lazy sequence therefore degrades a source's batched fetch to N scalar
reads — the exact pessimization the `get_items` hook exists to avoid.
Override each to delegate to `self._source.get_items([...])` (grouping
resolved indices by source for `ConcatSequence`); `ZippedSequence` already
implements the pattern. Value depends on sources implementing batch reads.

### `FileListSequence.files` snapshot caching (perf — needs a contract call)

`files` rebuilds `n` `Path` objects (plus `n` joins for
`FileFolderSequence`) on every access; the docstring advertises "a fresh
`tuple` on each access." Since `Path` / `tuple` are immutable, a cached
snapshot is observationally identical except for `is` identity. Build it
once (through `get_file`) and cache; reword the docstring. Deferred because
it is a deliberate, if benign, contract change.

---

*Last updated: 2026-06-07*

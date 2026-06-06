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

---

## 🌳 `kaparoo.filesystem.hierarchy`

### Validator / scaffolder (the remaining spec operations)

`match(tree, root)` has landed (`match.py`): it maps each on-disk path to
its spec node(s), honoring `depth` (backtracking, like a glob `**`) and
descending through `Group`s, reporting all overlapping matches. The
operations that build on it are not yet written — keep them as free
functions, nodes as pure value objects, reusing `search`'s traversal and
`stringify_path` where helpful:

- `validate(tree, root)` — conformance report: `matched`, `unexpected` (no
  node), `missing` (a `required` entry or required `Group` not satisfied),
  `violations` (`Exclusive` with >1 side present; `Together` partial).
- `conforms(tree, root)` — a `search` predicate ("keep spec-conforming
  paths"); the find-with-spec bridge.
- `scaffold(tree, root)` — write op: create the tree from `Expandable`
  names (and `required`).
- Cross-level "cell" exclusion (drop e.g. `(cam_01, frame_0003)` from a
  nested product) lands as a path-reject in `match`, not in the
  representation.

Policies to settle for the above:

- **`required` on an enumerable name** (`Template` / `OneOf`): "all expanded
  names present" or "at least one"?

`match` does not replace `search`: `search` *discovers* paths matching
stateless filters; `match` *checks / maps* a real tree against a known
structural spec (depth, constraints, presence). They share `kaparoo.filters`
and may share traversal, but answer different questions.

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

---

*Last updated: 2026-06-07*

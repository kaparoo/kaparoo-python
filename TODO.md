# TODO

Outstanding work not yet in code or tests. Promote an item to a CHANGELOG
entry once it lands.

---

## 🗂 `kaparoo.filesystem.hierarchy` — deferred items

Raised while working on 0.14.0 and deliberately left out of it.

### A separator in a `Filter` name is not rejected

`_as_filter` calls `_reject_separator` for the `str` / `list[str]` sugar but
passes an explicit `Filter` through untouched, so `Directory("a/b")` raises
while `Directory(Literal("a/b"))` — the same value — is accepted. Two
things then break, differently:

- `scaffold` raises `FileNotFoundError`, since `_make_dir` calls
  `path.mkdir()` without `parents=True` and the intermediate level is
  missing.
- `validate` / `locate` **silently never match**. `Entry.matches` compares
  against `path.name`, which never contains a separator, so the real
  directories are reported `unexpected` instead — a wrong signal, not an
  error.

Reached most plausibly by trying to flatten several levels into one
`Template("cam_{:02d}/{}", ...)`.

Only partly fixable: an `Expandable` name can be checked by expanding it,
but an open filter (`Glob("*/x")`, `Regex(r"a/b")`) cannot be decided in
general, and expanding a large `Template` at construction is not free.
Options are (a) check `Expandable` names only, (b) document that a `Filter`
name is the caller's responsibility, or (a)+(b). Do **not** simply add
`parents=True` to `_make_dir`: that fixes the crash and leaves the silent
validation mismatch, which is worse.

### `scaffold` cannot rewrite what is already there

`scaffold` is idempotent and never clobbers: `_make_file` returns early for
an existing file, so `on_create` never fires for it and there is no way to
refresh content. Creating only what is missing already works; recreating
does not.

Deferred because the composition below covers it with public API, and
because an `if_present` policy would introduce a data-loss window
(`touch()` then `on_create`) that this module currently does not have:

```python
for p, n in locate(spec, root):
    if not isinstance(n, File):
        continue
    if isinstance(n.name, Expandable) and n.is_direct_child:
        p.unlink()
scaffold(spec, root, on_create=fill)
```

The `Expandable` / `is_direct_child` filter is **required** and not obvious:
without it a `Glob`-matched file is deleted and `scaffold` cannot put it
back. That judgement lives in the private `Scaffolder._creatable`, so the
minimal fix is to expose it as `creatable(node)` and document the recipe,
leaving the non-destructive contract intact.

### Deriving a modified `Entry` drops the rest of its fields

There is no `dataclasses.replace` equivalent (the nodes are hand-rolled
immutable objects, not dataclasses), so the obvious reconstruction loses
every field not passed again — silently, since they all have defaults:

```python
d = Directory("ds", [File("a")], required=True, allow_extra=Glob(".*"),
              condition=ChildCount(min=1), depth=(1, 3))
Directory(d.name, [*d.children, File("b")])  # the four settings are gone
```

A single `replace()` on `Entry` (and `Group`, which has the same gap over
`required` / `on_conflict`) would fix it and make add / remove / update of
`children` one-liners. Mutating `add` / `remove` / `update` methods are the
wrong shape: the nodes are immutable, and `children` is an ordered tuple
that admits duplicates, so removal and update have no well-defined key.

Deferred: nothing in this package or in `iivs-cardio` derives a spec today.
Worth doing as soon as one does — building a spec from configuration, or
deriving a validation variant from a scaffolding one.

---

*Last updated: 2026-09-03*

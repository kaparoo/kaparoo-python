# TODO

Outstanding work not yet in code or tests. Promote an item to a CHANGELOG
entry once it lands.

---

## 📝 Make `required` on open names ("at least one match") explicit

`validate` already treats a `required` open-ended name (`Glob`, `Regex`, ...)
as "at least one matching path must exist": the node enters `present` the
moment it matches any path, so zero matches make it `missing` (confirmed by
hand, but undocumented and untested). Confirm this is the intended contract,
then document it -- the `validate` docstring / README currently spell out only
the enumerable `OneOf` / `Template` case -- and add a test. Note the asymmetry
with `scaffold`, which instead *raises* on an open-named `required` entry
because it cannot create one.

---

## 🐛 Settle `hierarchy.scaffold`'s atomicity / rollback contract

The structural rework is done -- helpers are `Scaffolder` methods, `visit`
owns root creation, and `root_as_top` is supported -- so a from-scratch
rewrite is no longer the plan. What remains is the **failure contract**: a
wrong-kind path (a file where a directory is described, or vice versa) raises
mid-run, leaving the paths already created on disk. Decide and implement the
contract -- best-effort (current, document it), pre-flight validation before
any write, or rollback of what this run created -- and cover it with tests.

---

## 📝 Unify docstrings to a consistent Google style

One style library-wide: imperative title, an optional summary, then `Args` /
`Returns` / `Yields` / `Raises` sections -- documenting intent and contracts,
not mechanism (per AGENTS.md).

---

*Last updated: 2026-06-19*

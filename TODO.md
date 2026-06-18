# TODO

Outstanding work not yet in code or tests. Promote an item to a CHANGELOG
entry once it lands.

---

## 🔍 Review `hierarchy.traverse.validate`

A rigorous correctness / edge-case / API-shape pass over `validate` and its
helpers (`_validate_as_top`, `_validate_under`, `_scan_under`, `_scan_frame`,
`_check_group`, `_classify_unexpected`, `_walk_nodes`, `_present_leaves`). The
locate part (`hierarchy.traverse.locate`) has already been reviewed.

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

*Last updated: 2026-06-18*

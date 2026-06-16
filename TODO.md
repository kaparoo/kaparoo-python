# TODO

Outstanding work not yet in code or tests. Promote an item to a CHANGELOG
entry once it lands.

---

## 🔍 Review `hierarchy.compare` — validation part

A rigorous correctness / edge-case / API-shape pass over `validate` and its
helpers (`_validate_at_root`, `_validate_under`, `_check_group`,
`_unexpected`, `_walk_nodes`, `_present_leaves`). The locate part has already
been reviewed.

---

## 🔨 Rewrite `hierarchy.scaffold` from scratch

Redesign and reimplement `scaffold` from the ground up rather than patching
it. Settle the atomicity / rollback contract on conflict as part of the
rewrite -- a wrong-kind path currently raises mid-run, leaving the
already-created paths on disk.

---

## 📝 Unify docstrings to a consistent Google style

One style library-wide: imperative title, an optional summary, then `Args` /
`Returns` / `Yields` / `Raises` sections -- documenting intent and contracts,
not mechanism (per AGENTS.md).

---

## 📖 Improve module-level README readability

Tighten each module's `README.md`: clearer public-API presentation,
idiomatic and copy-pasteable examples, public members over private.

---

*Last updated: 2026-06-17*

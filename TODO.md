# TODO

Outstanding work not yet in code or tests, by module. Promote an item to a
CHANGELOG entry once it lands.

---

## 🔍 Review the vibe-coded modules

A rigorous pass over modules first drafted quickly (AI-assisted), checking
correctness, edge cases, and API shape against the rest of the library:

- `kaparoo.filesystem.hierarchy` (*)

(*) highest priority — the largest or most intricate surface.

---

## 📝 Documentation pass (library-wide)

A consistency sweep over the prose, independent of the per-module review:

- **Docstrings** — rewrite to consistent Google style; replace
  mechanism-focused or over-written summaries with intent / contract per the
  AGENTS.md philosophy (one-line summary, then only what the signature
  cannot convey).
- **Comments** — shorten unnecessarily long comments to the load-bearing
  "why"; drop any that merely restate the code.
- **README.md** — improve how the public API is presented (description
  style) and tighten / fix the examples (idiomatic usage, public over
  private members, copy-pasteable).

---

## 🗂️ `kaparoo.filesystem.hierarchy` — contract decisions

These need a design call (and possibly a guard), not just a refactor:

### `scaffold` is not atomic on conflict (`scaffold.py`)

A wrong-kind path raises mid-run, leaving already-created paths on disk (no
rollback). Either document the no-rollback contract in `scaffold`'s docstring
and the README's scaffold section, or clean up the paths created so far.

---

## 🗑️ `kaparoo.filesystem.search` — remove the deprecated accessors

`get_paths` / `get_files` / `get_dirs` have been deprecated since 0.2.1 and
the library is now at 0.7.0 -- five minor releases of warnings. Remove the
`deprecated.py` module, its re-exports in `search/__init__.py` (and the
`get_*` names from `__all__`), the "Deprecation" section in
`search/README.md`, and `tests/filesystem/search/test_deprecated.py`. This
is an intended **breaking** change; land it in a minor release (e.g. with
the next breaking batch).

---

*Last updated: 2026-06-17*

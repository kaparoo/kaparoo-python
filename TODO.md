# TODO

Outstanding work not yet in code or tests, by module. Promote an item to a
CHANGELOG entry once it lands.

---

## 🧮 `kaparoo.utils.aggregate`

### Remove the `experimental` tag

The reduction family has now settled (`Stored` landed). When ready to commit
to SemVer stability, remove the `experimental` note from the module / class
docstrings, the CHANGELOG entry, and `kaparoo/utils/README.md`.

---

## 🗂️ `kaparoo.filesystem`

### Review cleanups (refactor -- behavior-preserving)

- **`_ensure_directory_target` does 2-3 stats per path in `make_dirs`** --
  apply the single-`exists`-then-`is_dir` shape (per-path only; caching
  `is_dir` across the validate->create gap changes behavior for nested
  paths, per the `make_dir` commit).

---

*Last updated: 2026-06-07*

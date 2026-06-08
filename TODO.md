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

## 🗂️ `kaparoo.filesystem.hierarchy` — refactors (behavior-preserving)

### Extract a `Variadic` base for `And` / `Or` (`conditions.py`)

`And` and `Or` differ only in the `all` / `any` reducer and an error string;
their `conditions` field, `__post_init__`, `_payload`, and `from_dict` are
byte-identical. Hoist the shared parts to a `Variadic(Condition)` base
(mirroring `Bound`), with each subclass supplying only the reducer -- the
same pattern the metadata-condition family already uses.

### Build the `exclude` predicate once in `validate` (`validate.py`)

`validate` re-normalizes its `exclude=` argument repeatedly: every
`match_map` call (one per top node) rebuilds the excluder via
`build_excluder`, then `_build_report` builds it again for `_unexpected`.
Build it once in `_build_report` and thread the resulting predicate down
into `match` / `match_map` / `_unexpected`. `build_excluder` is already the
shared seam, so behavior is unchanged; keep `match`'s public `exclude=`
signature intact.

---

*Last updated: 2026-06-08*

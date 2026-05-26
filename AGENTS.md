# Agent guide — `kaparoo-python`

Guidance for AI coding assistants working on this project.
`CLAUDE.md` loads this file via the `@AGENTS.md` import.

## Project

- Package: `kaparoo/`
- Python:  3.14+
- Kind:    distributable library (`uv_build` backend)

## Toolchain

The Astral toolchain — keep it unless there is a clear reason to change:

- `uv`   — environment, locking, running
- `ruff` — linting + formatting
- `ty`   — type checking
- `pytest` — testing

## Commands

```bash
uv sync --group dev      # create/refresh the environment
uv run ruff check .      # lint
uv run ruff format .     # format
uv run ty check          # type-check
uv run pytest            # run tests
```

## Conventions

- Keep code fully typed — `ty` runs with `error-on-warning`.
- Fix `ruff` findings rather than suppressing them, unless there is a
  clear, commented reason.
- Tests live in `tests/` and may use bare `assert` (ruff `S101` is
  waived there).
- `ty` has no plugin system; rely on standard typing (PEP 681
  `dataclass_transform`, `.pyi` stubs), not type-checker plugins.

## Python style

`ruff` enforces most of this — run `uv run ruff check --fix` rather than
applying it by hand.

- Every module starts with `from __future__ import annotations` (ruff
  isort `required-imports`). Empty `__init__.py` package markers are
  exempt.
- Use builtin generics — `list`, `dict`, `tuple`, `type` — never
  `typing.List`, `typing.Dict`, `typing.Tuple`, `typing.Type` (ruff `UP`).
- Imports are grouped and sorted: standard library, third party, first
  party, then a trailing `if TYPE_CHECKING:` block (grouped the same
  way). Within a group `import X` precedes `from X import Y`; entries are
  alphabetical.
- Docstrings are optional — write them where they clarify intent, not
  mechanically on every function, class, or method. When written, use
  [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
  (`Args:` / `Returns:` / `Raises:` sections), and omit types from
  `Args:` entries — the signature already carries them.
- Standalone runnable scripts carry PEP 723 inline metadata (the
  `# /// script` block). `uv` manages it (`uv add --script`); add or edit
  it by hand only when explicitly asked.

## Commit convention

Commit messages use a [Gitmoji](https://gitmoji.dev/) prefix and wrap
package/tool names in backticks:

```
<emoji> <Imperative summary; tool names in `backticks`>

<Optional body explaining *why*>
```

Common prefixes in this project:

| Prefix | Use for                                       |
| ------ | --------------------------------------------- |
| ✨     | New feature                                   |
| ♻️     | Refactor (no user-visible behavior change)    |
| 🔥     | Remove dead / vestigial code                  |
| 🐛     | Bug fix                                       |
| 📝     | Docstrings, README, CHANGELOG                 |
| ✏️     | Typo or other small text fix                  |
| 💄     | Style (no behavior change)                    |
| ✅     | Tests added or updated                        |
| ⚡     | Performance optimization                      |
| 🏷️     | Type-hint-only change                         |
| 💬     | Code comment                                  |
| 🗑️     | Deprecation signal                            |
| 📦     | Re-export / packaging structure               |
| 🚚     | Move / rename files                           |
| ⬆️     | Bump a dependency or tool version             |
| 🔧     | Config (`pyproject.toml`, `ruff`, `ty`, ...)  |
| 🔖     | Release a version (commit + matching tag)     |

Keep commits single-purpose; don't rewrite published history; don't
skip git hooks. AI assistants append a `Co-Authored-By` trailer with
their own published identity (e.g. `Claude <noreply@anthropic.com>`).

## Releases

`0.x.y` follows SemVer; in pre-1.0, a minor bump may carry breaking
changes. Release procedure for `X.Y.Z`:

1. Move `CHANGELOG.md`'s `[Unreleased]` content into a dated
   `[X.Y.Z] - YYYY-MM-DD` section. Drop entries whose subject was both
   introduced *and* renamed / removed / fixed within the same cycle --
   upgraders never saw the intermediate state, so it does not belong
   in the changelog.
2. Bump `version` in `pyproject.toml`; `uv sync --group dev` to
   refresh `uv.lock`.
3. Commit: `🔖 Release version X.Y.Z`, body referencing the new
   `[X.Y.Z]` CHANGELOG entry.
4. `uv build`. Validate with `uvx twine check dist/*` and a fresh
   install in an isolated environment
   (`uv run --isolated --no-project --with dist/*.whl python -c "..."`).
5. Publish to TestPyPI first:
   `uv publish --index testpypi --username __token__ --keyring-provider subprocess`.
   Verify the project page and a fresh install from
   `test.pypi.org/simple/`.
6. Publish to PyPI with the same command using `--index pypi`.
7. Annotated tag `vX.Y.Z` whose message starts with
   `🔖 Release version X.Y.Z` and references the CHANGELOG; push the
   tag.

Tokens live in the OS keyring at the `publish-url` key (`keyring set
<publish-url> __token__`), scoped per-project once the package exists
on the index. Named indexes (`pypi`, `testpypi`) are configured under
`[[tool.uv.index]]` in `pyproject.toml`; `testpypi` carries
`explicit = true` so it stays out of dependency resolution.

## Template

Generated from a copier template. `.copier-answers.yml` records the
answers; run `copier update --UNSAFE` to pull later template changes.

---

<!-- Add project-specific guidance below. -->

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
- `pytest-cov` — coverage measurement and threshold gate

## Commands

```bash
uv sync --group dev      # create/refresh the environment
uv run ruff check .      # lint
uv run ruff format .     # format
uv run ty check          # type-check
uv run pytest            # run tests (coverage included by default)
uv run pytest --no-cov   # skip coverage for quick iteration
```

Coverage is measured by `pytest-cov` against `kaparoo/` with branch
tracking; a `fail_under` gate is configured in `pyproject.toml`.

## Conventions

- Keep code fully typed — `ty` runs with `error-on-warning`.
- Fix `ruff` findings rather than suppressing them, unless there is a
  clear, commented reason.
- Tests live in `tests/` and may use bare `assert` (ruff `S101` is
  waived there).
- **Tests mirror the source tree.** A source file
  `kaparoo/<pkg>/<mod>.py` is tested at `tests/<pkg>/test_<mod>.py`;
  a subpackage `kaparoo/<pkg>/<sub>/` is tested under
  `tests/<pkg>/<sub>/`. Not every source file needs a dedicated test
  file — types-only modules, re-export `__init__.py` markers, and
  implementation details covered through a public-facing module are
  intentional exceptions. Cross-module test helpers live in
  `tests/<pkg>/helpers.py`, shared fixtures in `tests/fixtures/`,
  and per-package pytest configuration in `conftest.py`.
- `ty` has no plugin system; rely on standard typing (PEP 681
  `dataclass_transform`, `.pyi` stubs), not type-checker plugins.
- **Submodule READMEs own the usage examples.** The root `README.md` is
  a hub: brief module overview + links to each submodule's `README.md`.
  When documenting a new public API, add the example to the nearest
  submodule README (e.g. `kaparoo/filesystem/search/README.md`) rather
  than the root.

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
- Within a function body, separate logical groups with a single blank
  line and put a blank line before the final `return`; leave a tightly
  coupled one- or two-line body unbroken (see `utils/timer.py`).
- In a long module, group related definitions under a boxed comment
  banner — a centred title between two `#`-bordered rules — as in
  `filesystem/directory.py` and `utils/aggregate.py`.
- Docstrings are optional — write them where they clarify intent, not
  mechanically. "Mechanically" targets two habits to avoid: comments (or
  docstrings) that merely restate the code, and a base class whose
  docstring explains itself in terms of its specific subclasses. It is
  *not* a licence to leave a consumed method bare. When written, document
  *intent and contracts, not mechanism*:
  - Lead with a one-line summary — declarative noun phrase for
    classes ("An ordered, lazily-loaded, read-only sequence ..."),
    imperative verb phrase for functions and methods ("Yield sliding
    windows from `sequence`.").
  - A concrete public method that callers consume (`Mean.step`,
    `Var.merge`) must be **self-explainable** from its own docstring and
    signature — never lean on an inherited parent docstring to carry it.
    Abstract base methods document only the generic contract and never
    name a specific subclass.
  - Surface what callers cannot infer from the signature alone:
    invariants, edge cases, what subclasses must override, policy
    trade-offs. Skip restating what the code already shows.
  - Use [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
    sections (`Args:`, `Returns:`, `Yields:`, `Raises:`,
    `Type Parameters:`); omit types from `Args:` since the signature
    carries them. Custom sections (`Parameterized subclasses:`,
    `Truth table:`, `Example:`) are welcome when they clarify a real
    pitfall or pattern.
  - Add an `Args:` / `Returns:` block only for what the summary and
    signature cannot already convey — a parameter constraint, a
    non-obvious or edge-case return. When they make the behaviour obvious
    (a no-argument getter, or a self-evident one-liner), the one-line
    summary *is* the whole docstring; a `Returns:` that merely restates it
    is the mechanical habit above. Document an edge case shared across a
    family (e.g. the empty-stream value) once on the class, not on every
    method.
  - Reference identifiers in backticks (`get_item`, `size`,
    `Filter.parse`).
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
changes.

Releases are automated by
[`.github/workflows/publish.yml`](./.github/workflows/publish.yml):
pushing an annotated tag matching `v*.*.*` triggers CI verification,
a sdist+wheel build (`uv build` + `twine check`), then TestPyPI and
PyPI publishes via `pypa/gh-action-pypi-publish`. Both publish steps
use GitHub's OIDC trusted-publishing flow -- no API tokens are stored
anywhere. The PyPI step is gated by the GitHub `pypi` environment,
which has a manual approval rule, so PyPI never ships without a human
reviewing the TestPyPI artifact first.

Release procedure for `X.Y.Z`:

1. Move `CHANGELOG.md`'s `[Unreleased]` content into a dated
   `[X.Y.Z] - YYYY-MM-DD` section. Drop entries whose subject was both
   introduced *and* renamed / removed / fixed within the same cycle --
   upgraders never saw the intermediate state, so it does not belong
   in the changelog.
2. Bump `version` in `pyproject.toml`; `uv sync --group dev` to
   refresh `uv.lock`.
3. Commit `🔖 Release version X.Y.Z` with a body referencing the new
   `[X.Y.Z]` CHANGELOG entry.
4. `git push origin main`. The push-to-main `ci.yml` workflow runs
   ruff + ty + pytest across the OS matrix; wait for it to go green.
5. Create an annotated tag `vX.Y.Z` whose message starts with
   `🔖 Release version X.Y.Z` and references the CHANGELOG; push it
   with `git push origin vX.Y.Z`. The publish workflow starts.
6. After the TestPyPI job finishes, verify the published artifact in
   a clean environment before approving the PyPI step. From any shell
   (PowerShell shown):
   ```powershell
   uv run --isolated --no-project --refresh-package kaparoo-python --default-index https://test.pypi.org/simple/ --with 'kaparoo-python==X.Y.Z' python -c "from importlib.metadata import version; assert version('kaparoo-python') == 'X.Y.Z'; print('OK')"
   ```
   Extend the smoke checks to import and exercise whatever the release
   actually touches (new submodule, renamed symbol, fixed bug, ...).
7. Approve the `pypi` environment in the GitHub Actions UI to release
   the PyPI publish step. The job uploads to PyPI via OIDC.

Named indexes (`pypi`, `testpypi`) are configured under
`[[tool.uv.index]]` in `pyproject.toml`; `testpypi` carries
`explicit = true` so it stays out of normal dependency resolution.
The only consumers of those named indexes today are this verification
step (which targets `testpypi` via `--default-index`) and any
emergency manual publish (`uv publish --index <name>
--keyring-provider subprocess` with an API token in the OS keyring at
the `publish-url` key). Normal releases never go through that manual
path.

## Template

Generated from a copier template. `.copier-answers.yml` records the
answers; run `copier update --UNSAFE` to pull later template changes.

---

<!-- Add project-specific guidance below. -->

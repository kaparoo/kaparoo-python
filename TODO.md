# TODO

Tracked items that are not yet captured in code or tests. Promote an
item to a CHANGELOG entry once it lands.

## Open

- [ ] **`kaparoo.data` module** — design and implement the data utilities
      sub-package (currently a placeholder).
- [ ] **CI workflow** — add `.github/workflows/ci.yml` running
      `ruff format --check`, `ruff check`, `ty check`, and `pytest` on
      push and pull request.
- [ ] **Coverage measurement** — formalize via `pytest-cov` (or
      `coverage.py`) with a `[tool.coverage.*]` section in
      `pyproject.toml`; consider a minimum threshold gate.

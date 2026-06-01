# `kaparoo.filesystem`

`pathlib`-based filesystem helpers.

## Modules

- [`existence`](./existence.py) — boolean predicates (`*_exists`) and
  validating `ensure_*` variants
- [`directory`](./directory.py) — `make_dir(s)`, `dir_empty(s)` /
  `dir_not_empty(s)` with validation, plus `_unsafe` variants that skip
  pre-checks
- [`utils`](./utils.py) — `stringify_path(s)`, `wrap_path(s)`
- [`exceptions`](./exceptions.py) — `DirectoryNotFoundError`, `NotAFileError`
- [`types`](./types.py) — `StrPath`, `StrPaths` type aliases
- [`search/`](./search/) — composable filesystem search (own README)

All public symbols are re-exported from the top-level `kaparoo.filesystem`
namespace.

## Existence checks

`*_exists` return a bool; `ensure_*` raise on failure and return the
(optionally stringified) path.

```python
from kaparoo.filesystem import (
    dir_exists, ensure_dir_exists, ensure_files_exist, file_exists,
)

if file_exists("config.toml"):
    ...

# Single path: raises FileNotFoundError / NotAFileError / NotADirectoryError
config = ensure_dir_exists("var/cache", make=True)  # create if missing
report = ensure_dir_exists("var/cache", make=0o755)  # mode bits: POSIX only

# Bulk with a shared root; each entry is resolved relative to it.
files = ensure_files_exist(
    ["a.txt", "b.txt"],
    root="data",
)
```

## Exception hierarchy

`DirectoryNotFoundError` subclasses `FileNotFoundError`, so callers may
catch the broader type:

```python
from kaparoo.filesystem import DirectoryNotFoundError, ensure_dir_exists

try:
    ensure_dir_exists("var/missing")
except FileNotFoundError:  # catches DirectoryNotFoundError too
    ...
```

## Creating and emptying directories

```python
from kaparoo.filesystem import (
    dir_empty, dir_not_empty, dirs_empty, make_dir, make_dirs,
)

cache_dir = make_dir("var/cache", exist_ok=True)

# Bulk creation with a shared root
make_dirs(["logs", "tmp"], root="var", exist_ok=True)

# Empty checks (raise if missing or not a directory)
assert dir_empty(cache_dir)
assert dirs_empty(["logs", "tmp"], root="var")

# ...and their negations
(cache_dir / "data.bin").touch()
assert dir_not_empty(cache_dir)
```

Each check has a negated counterpart (`dir_not_empty`, `dirs_not_empty`);
`dirs_not_empty` is True only when *every* directory is non-empty. The
`_unsafe` variants (`dir_empty_unsafe`, `dir_not_empty_unsafe`,
`dirs_empty_unsafe`, `dirs_not_empty_unsafe`) skip existence/type
validation and are intended for hot paths where the caller has already
validated.

## Path manipulation

`stringify_path(s)` converts to forward-slash strings, optionally
trimming a leading or trailing portion. `wrap_path(s)` prepends and/or
appends path components, rejecting absolute inputs where ambiguous.

```python
from pathlib import Path
from kaparoo.filesystem import stringify_path, stringify_paths, wrap_path

# "path/to/file.txt" on every platform (including Windows)
stringify_path(Path("path") / "to" / "file.txt")

# Trim leading or trailing components
stringify_path("a/b/c", after="a")     # "b/c"
stringify_path("a/b/c", before="c")    # "a/b"

# Bulk stringify with a shared base.
stringify_paths(["data/a.txt", "data/b.txt"], after="data")  # ["a.txt", "b.txt"]

# Compose paths without joining manually
wrap_path("logs", prepend="var", append="server.log")  # var/logs/server.log
```

## Platform notes

- **Directory mode bits**: `mode` (on `make_dir` / `make_dirs`) and
  `make=<int>` (on `ensure_dir_exists` / `ensure_dirs_exist`) are
  validated against the `0o1`–`0o7777` range and applied to the created
  directory on **POSIX systems only**. On Windows, mode values are still
  accepted (so cross-platform code stays clean) but the range check is
  skipped and the OS ignores the bits — see
  [`os.mkdir`](https://docs.python.org/3/library/os.html#os.mkdir).
- **Path separators**: `stringify_path` and `stringify_paths` normalize
  backslashes to forward slashes on Windows. Functions that return
  strings via `stringify=True` (`make_dir`, `ensure_dir_exists`,
  `wrap_path`, ...) inherit this normalization. If you need a native
  Windows path string, call `str(path)` directly on a `Path`.

## See also

- [`search/`](./search/) for filesystem traversal with filters
- [`kaparoo.utils`](../utils/) for `Timer` and Optional helpers

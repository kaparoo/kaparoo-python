# `kaparoo.filesystem`

`pathlib`-based filesystem helpers.

## Modules

- [`existence`](./existence.py) — boolean predicates (`*_exists`) and
  validating `ensure_*` variants
- [`directory`](./directory.py) — `make_dir(s)`, `dir_empty(s)` /
  `dir_not_empty(s)` with validation, plus `_unsafe` variants that skip
  pre-checks
- [`utils`](./utils.py) — `stringify_path(s)`, `wrap_path(s)`,
  `reserve_path(s)`
- [`temporary`](./temporary.py) — `TemporaryFile`, a scratch temp file
  usable as a context manager or explicitly
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

# Start from a clean slate: wipe an existing directory's contents and
# recreate it empty. Destructive, and only ever wipes a *directory* (a
# non-directory at the path still raises). `clean=True` makes `exist_ok`
# moot, since the directory is removed and remade.
run_dir = make_dir("out/run_42", clean=True)

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

## Reserving a destination

`reserve_path` guards a path that should *not* yet exist, so you don't
clobber something when creating a new file or directory there. It only
checks (and optionally creates the parent) — it never creates or deletes
the target itself.

```python
from kaparoo.filesystem import reserve_path

# Raises FileExistsError if out/run.json exists; otherwise creates the
# missing parent directory and returns the path ready to write to.
out = reserve_path("out/run.json", make_parents=True)
out.write_text("{}")

# `exist_ok` (named as in make_dir / Path.mkdir) is a non-destructive
# bypass: it suppresses the conflict but deletes nothing, so a later write
# overwrites in place.
out = reserve_path("out/run.json", exist_ok=True)

# `reserve_paths` is the bulk form (fail-fast on the first conflict). It
# takes no `root`; compose with `wrap_paths` to share a base directory.
from kaparoo.filesystem import reserve_paths, wrap_paths
a, b = reserve_paths(wrap_paths(["a.bin", "b.bin"], prepend="out"))
```

For a *directory* destination, `make_dir(..., exist_ok=...)` both guards
and creates it; for an exclusive *file* create, the stdlib `open(path,
"x")` raises the same `FileExistsError` directly. Reach for `reserve_path`
when you want the check (and parent setup) decoupled from the creation.

`reserve_path` is intentionally **non-destructive** — it never removes an
existing target. To start a directory from a clean slate, use the
`clean` option on `make_dir` / `make_dirs` (see below), which is the only
destructive operation here and is named to say so.

## Temporary files

`TemporaryFile` is a scratch temporary file — a real, named file opened in
binary `w+b` mode that is removed when closed. It works both as a context
manager and explicitly (like a file object), and is cleaned up even if you
forget to close it (a `weakref` finalizer runs on garbage collection).

```python
from kaparoo.filesystem import TemporaryFile

# Context manager — removed on exit.
with TemporaryFile() as tmp:
    tmp.write(b"scratch")
    tmp.seek(0)
    data = tmp.read()
    print(tmp.path)  # the Path, valid inside the block

# Explicit — close() removes it; close() is idempotent.
tmp = TemporaryFile(directory="var", suffix=".bin")
tmp.write(b"...")
tmp.close()

# Keep the file: delete=False leaves it at `path` for you to move/rename.
tmp = TemporaryFile(delete=False)
tmp.close()
final = tmp.path  # still on disk
```

It is binary-only; for text, wrap `tmp.file` (the underlying handle) in an
`io.TextIOWrapper` or encode before writing. While open, reopening
`tmp.path` by name may fail on Windows — write through the object.

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

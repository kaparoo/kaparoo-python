# `kaparoo.data`

Building blocks for dataset code: a `Sequence`-based abstract base, a
small set of composers, and ready-to-subclass file-backed templates.

## Modules

- [`sequences/base`](./sequences/base.py) — `DataSequence[T, M]` abstract base
- [`sequences/composers`](./sequences/composers.py) — `SlicedSequence`,
  `TransformedSequence`, `ConcatSequence`, `WindowedSequence`,
  `ZippedSequence`
- [`sequences/templates`](./sequences/templates.py) — `FileFolderSequence`,
  `FileListSequence`, `SingleFileSequence`
- [`sequences/utils`](./sequences/utils.py) — `generate_batches`

All public symbols are re-exported from both `kaparoo.data` and
`kaparoo.data.sequences`.

## DataSequence

`DataSequence[T, M]` is a `Sequence[T]` ABC that adds a parallel
metadata channel. Subclasses implement two abstract methods:

| Method | Purpose |
| --- | --- |
| `get_item(index) -> T` | Decode the i-th item. |
| `get_meta(index) -> M` | Produce the i-th item's metadata. |

The base derives `get_items` / `get_metas` (bulk) and `get_pair` /
`get_pairs` (item + metadata together). `__getitem__` returns the item
only — slicing yields a `SlicedSequence`. The `M` type parameter
defaults to `None`; set it explicitly when items carry meaningful
metadata (paths, labels, line numbers, ...).

```python
from kaparoo.data.sequences import DataSequence

class Labeled(DataSequence[bytes, str]):
    def __init__(self, items, labels):
        self._items = items
        self._labels = labels

    def __len__(self):
        return len(self._items)

    def get_item(self, index):
        return self._items[index]

    def get_meta(self, index):
        return self._labels[index]

ds = Labeled([b"a", b"b"], ["cat", "dog"])
ds[0]                # b"a"           (item only)
ds.get_pair(0)       # (b"a", "cat")  (item + metadata)
list(ds.get_metas([0, 1]))  # ["cat", "dog"]
```

## Composers

### `SlicedSequence`

A stable-length view over `source` exposing only items at the given
`indices`. `indices` is materialized as a tuple, so `len()` is O(1) and
random access is O(1) into the index table. **Duplicates are allowed,
order is preserved.**

```python
from kaparoo.data.sequences import SlicedSequence

view = SlicedSequence(dataset, [3, 7, 11])
view[0]   # == dataset[3]
view[1]   # == dataset[7]
```

### `ConcatSequence`

End-to-end concatenation of zero or more sources. Lookup is O(log N) in
the number of sources via cumulative-length `bisect_right`.

```python
from kaparoo.data.sequences import ConcatSequence

combined = ConcatSequence(train_a, train_b, train_c)
len(combined)  # == len(train_a) + len(train_b) + len(train_c)
```

### `TransformedSequence`

A lazy view that applies a `transform` callable to each item of
`source`. The transform is called on demand in `get_item` -- nothing
is computed at construction. `get_meta` passes through `source.get_meta`
unchanged by default; override it in a subclass when `M_out` differs
from `M_in`. **That override is required, not optional**: if you declare a
different `M_out` but forget it, the default silently returns the source's
`M_in` metadata typed as `M_out` (a `cast` hides the mismatch, and Python
erases generics at runtime, so nothing catches it until the wrong value is
used).

```python
from kaparoo.data.sequences import TransformedSequence

# Item transform only -- metadata type is unchanged.
normalized = TransformedSequence(image_folder, normalize_fn)

# Meta transform via subclassing:
class Augmented(TransformedSequence[ndarray, Path, ndarray, AugMeta]):
    def get_meta(self, index: int) -> AugMeta:
        return AugMeta(path=self.source.get_meta(index), applied="normalize")
```

Chaining two `TransformedSequence` instances applies the transforms in
order:

```python
resized    = TransformedSequence(raw, resize)
normalized = TransformedSequence(resized, normalize)
```

`T_out` and `M_out` default to `T_in` and `M_in` respectively (PEP 696),
so you only need to specify them when the type actually changes.

### `WindowedSequence`

An abstract sliding-window view: each item is a `tuple[T, ...]` of
`size` frames from `source`. Per-frame `M_in` and window-level
`M_out` are independent type parameters (`M_out` defaults to `M_in`),
so subclasses decide how metadata aggregates.

```python
from pathlib import Path
from kaparoo.data.sequences import WindowedSequence

class FirstFrameMeta(WindowedSequence[bytes, Path]):
    def get_meta(self, index):
        # window's metadata is its first frame's metadata
        index = self._normalize_index(index)
        return self._source.get_meta(index * self._step)

# 3-frame windows, hop 1, no intra-window skip
windows = FirstFrameMeta(frames, size=3)
windows[0]            # (frames[0], frames[1], frames[2])
windows.get_meta(0)   # frames.get_meta(0)
```

`size`, `step`, `skip` follow the same semantics as
[`generate_batches`](#generate_batches).

### `ZippedSequence`

Element-wise zip of two sequences — item `i` is `(first[i], second[i])`
and metadata `i` is the `(M1, M2)` tuple. This is the "paired image +
label" pattern that `ConcatSequence` (end-to-end) cannot express. With
`strict=True` (the default) the lengths must match or construction raises
`ValueError`; pass `strict=False` to truncate to the shorter length, like
the builtin `zip`. For a different combined metadata shape, subclass and
override `get_meta`.

```python
from kaparoo.data.sequences import ZippedSequence

pairs = ZippedSequence(images, labels)
pairs[0]            # (images[0], labels[0])
pairs.get_meta(0)   # (images.get_meta(0), labels.get_meta(0))
```

For three or more, nest: `ZippedSequence(a, ZippedSequence(b, c))` yields
`(a[i], (b[i], c[i]))`.

## Templates

### `FileFolderSequence`

Folder-rooted base for "one file per item" datasets. Subclasses
implement three methods:

- `list_files(self, root)` — return the full `Path` of every file to
  expose, in order. Called once from the base's `__init__`. Every
  returned path must be under `root`.
- `load_file(self, path)` — decode a single file. Called lazily on each
  `get_item`.
- `get_meta(self, index)` — per-item metadata. When metadata is the
  source path, `M` defaults to `Path` and `get_meta` can be
  `return self.get_file(index)`.

The base exposes `root: Path`, `files: tuple[Path, ...]` (fresh snapshot),
and `get_file(index) -> Path`. Paths are stored root-relative
internally, so the sequence stays compact and survives a relocated root.

**Parameterized subclasses**: when `list_files` needs instance options
(patterns, recursive flags, ...), set them on `self` **before** calling
`super().__init__(root)` — the base invokes `list_files` from its own
`__init__`.

```python
from pathlib import Path
from kaparoo.data.sequences import FileFolderSequence

class GlobFolder(FileFolderSequence[bytes]):
    def __init__(self, root, *, pattern="*", recursive=False):
        # Set state BEFORE super().__init__() so list_files can read it.
        self._pattern = pattern
        self._recursive = recursive
        super().__init__(root)

    def list_files(self, root):
        glob_fn = root.rglob if self._recursive else root.glob
        return sorted(p for p in glob_fn(self._pattern) if p.is_file())

    def get_meta(self, index):
        return self.get_file(index)

    def load_file(self, path):
        return path.read_bytes()

folder = GlobFolder("data", pattern="*.png", recursive=True)
```

### `FileListSequence`

Same "one file per item" contract as `FileFolderSequence`, but the files
are given as an explicit list instead of discovered under a `root` — so
they may live in unrelated directories (or, on Windows, different drives),
which `FileFolderSequence` cannot represent. There is no `list_files`;
subclasses implement only `load_file` and `get_meta`. The input order is
preserved verbatim (duplicates kept) — sort it yourself if needed.

```python
from pathlib import Path
from kaparoo.data.sequences import FileListSequence

class BytesList(FileListSequence[bytes]):
    def get_meta(self, index):
        return self.get_file(index)

    def load_file(self, path):
        return path.read_bytes()

# Files from anywhere, in the order given:
data = BytesList(["images/a.png", "/other/disk/b.png"])
```

### `SingleFileSequence`

Thin ABC for the "one file, many records" pattern (a video with many
frames, a CSV with many rows, ...). The base validates that `path`
exists and is a regular file and exposes it via the `path` property.
Indexing strategies vary too widely across formats to abstract here —
subclasses own opening, indexing, and decoding.

```python
from kaparoo.data.sequences import SingleFileSequence

class LinesFile(SingleFileSequence[str, int]):
    def __init__(self, path):
        super().__init__(path)
        self._lines = tuple(self.path.read_text().splitlines())

    def __len__(self):
        return len(self._lines)

    def get_item(self, index):
        return self._lines[index]

    def get_meta(self, index):
        return index + 1  # 1-based line number
```

## generate_batches

A windowing iterator over any `Sequence`. `size` is the only positional
parameter; `step` / `skip` / `start` / `stop` / `drop_last` are
keyword-only.

| Parameter | Effect |
| --- | --- |
| `size` | items per window |
| `step` *(default 1)* | distance between consecutive windows |
| `skip` *(default 1)* | intra-window stride |
| `start`, `stop` | restrict the source range; `start == stop` yields nothing |
| `drop_last` *(default `True`)* | drop a trailing partial window if any |

```python
from kaparoo.data.sequences import generate_batches

# Overlapping 3-windows (default step=1)
list(generate_batches(range(6), size=3))
# [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]]

# Non-overlapping batches
list(generate_batches(range(7), size=3, step=3, drop_last=False))
# [[0, 1, 2], [3, 4, 5], [6]]
```

## See also

- [`kaparoo.filesystem`](../filesystem/) for path helpers and search
- [`kaparoo.utils`](../utils/) for `Timer` and Optional helpers

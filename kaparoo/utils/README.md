# `kaparoo.utils`

Small, focused helpers — not enough material for their own packages.

## Modules

- [`timer`](./timer.py) — `Timer`, `LapTimer`, `LapRecord`
- [`optional`](./optional.py) — helpers for `T | None` values

## Timer

`Timer` measures one elapsed duration. It works both as a context
manager and as a decorator. `unit` selects the reporting unit
(`"s" | "ms" | "us" | "ns"`); `ndigits` controls rounding.

```python
from kaparoo.utils.timer import Timer

# As a context manager
with Timer("ms", ndigits=2) as t:
    do_work()
print(f"Took {t.elapsed} ms")

# As a decorator (each call overwrites `t.elapsed`)
t = Timer("ms")

@t
def load() -> None: ...

load()
print(t.elapsed)
```

### Pause / resume / suspend

Exclude a region from the measured interval. `suspend()` is a
context-manager equivalent of `pause()` + `resume()` (it skips the
auto-resume if the user already resumed manually).

```python
with Timer("ms") as t:
    do_setup()
    with t.suspend():
        prompt_user_interactively()   # excluded from t.elapsed
    do_work()
```

## LapTimer

`LapTimer` extends `Timer` with named intermediate timings. Every call
to `lap(label)` produces a `LapRecord` (a `TypedDict` with `label`,
`lap_time`, `total_time`).

```python
from kaparoo.utils.timer import LapTimer

with LapTimer("ms", ndigits=1) as lt:
    step_a()
    lt.lap("A")
    step_b()
    lt.lap("B")

# Per-lap details:
for record in lt.records:
    print(record["label"], record["lap_time"])

# Aggregated by label (sums `lap_time` for repeated labels):
print(lt.summary)   # e.g. {"A": 12.3, "B": 8.7}
print(lt.elapsed)   # total wall time of the `with` block
```

### Same-label policies

| `on_same_label` | Behavior on a repeated label |
| --- | --- |
| `"merge"` *(default)* | record as-is; `summary` aggregates the duplicates |
| `"separate"` | append a `" (N)"` suffix to keep records distinct |
| `"reject"` | raise `ValueError` |

```python
with LapTimer(on_same_label="separate") as lt:
    lt.lap("A")
    lt.lap("A")   # recorded as "A (2)"
    lt.lap("A")   # recorded as "A (3)"
```

## Optional helpers

For when `value if value is not None else default` accumulates and an
expression form reads better. The `unwrap_or_*` variants additionally
apply an optional transform to the result.

```python
from kaparoo.utils.optional import (
    factory_if_none, replace_if_none, unwrap_or_default,
)

# Pick the surrogate when the value is None
replace_if_none(maybe_name, "anonymous")

# Same, but compute the default lazily
factory_if_none(maybe_config, lambda: load_default_config())

# Transform either branch with the same callable
unwrap_or_default(maybe_text, "default", str.upper)  # always uppercased
```

For sequences, the `unwrap_or_defaults` / `unwrap_or_factories` variants
operate element-wise and return a `list`.

```python
from kaparoo.utils.optional import unwrap_or_defaults

unwrap_or_defaults([None, "x", None], "y")        # ["y", "x", "y"]
unwrap_or_defaults([None, "x"], "y", str.upper)   # ["Y", "X"]
```

## See also

- [`kaparoo.filesystem`](../filesystem/) for filesystem helpers
- [`kaparoo.filesystem.search`](../filesystem/search/) for traversal

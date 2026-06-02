# `kaparoo.utils`

Small, focused helpers — not enough material for their own packages.

## Modules

- [`timer`](./timer.py) — `Timer`, `SegmentTimer`, `SegmentRecord`
- [`aggregate`](./aggregate.py) — `Aggregator` + the `Reduction` family
  (`Mean`, `Sum`, `Min`, `Max`, `Last`, `Fold`)
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

## SegmentTimer

`SegmentTimer` extends `Timer` with named time *segments*. Each segment
is a `SegmentRecord` (a `TypedDict` with `label`, `duration`,
`total_time`) and is produced in one of two ways:

- **`lap(label)` — split.** Each lap's `duration` is the time since the
  previous lap (or the start), so every instant belongs to exactly one
  segment.
- **`measure(label)` — stopwatch.** Times only the wrapped block; time
  spent outside any `measure` block is attributed to no segment.

```python
from kaparoo.utils.timer import SegmentTimer

with SegmentTimer("ms", ndigits=1) as st:
    step_a()
    st.lap("A")               # split: time since start
    idle()                    # NOT counted by the next measure
    with st.measure("B"):     # stopwatch: only this block
        step_b()

# Per-segment details:
for record in st.records:
    print(record["label"], record["duration"])

# Aggregated by label (sums `duration` for repeated labels):
print(st.summary)   # e.g. {"A": 12.3, "B": 8.7}
print(st.elapsed)   # total wall time of the `with` block
```

### `lap` vs `measure`

`lap` splits the timeline into contiguous segments — the gap before a
lap is folded into that lap. `measure` brackets a region and ignores
everything outside it, so untimed work between blocks is excluded from
`summary`. Pick `lap` for back-to-back phases, `measure` for discrete
operations interleaved with untimed work. Pauses inside either are
excluded; a `measure` block that raises records nothing.

`measure` doubles as a decorator (every decorated call records one
segment, as long as the timer is running when it is called):

```python
st = SegmentTimer("ms")

@st.measure("load")
def load() -> None: ...

with st:
    load()        # records a "load" segment each call
```

### Same-label policies

| `on_same_label` | Behavior on a repeated label |
| --- | --- |
| `"merge"` *(default)* | record as-is; `summary` aggregates the duplicates |
| `"separate"` | append a `" (N)"` suffix to keep records distinct |
| `"reject"` | raise `ValueError` |

The policy applies to both `lap` and `measure`:

```python
with SegmentTimer(on_same_label="separate") as st:
    st.lap("A")
    st.lap("A")   # recorded as "A (2)"
    st.lap("A")   # recorded as "A (3)"
```

## Aggregation

> **🚧 Work in progress** — this API is experimental and may change or be
> removed before the next release. It is not yet covered by the project's
> SemVer guarantees.

`Aggregator` accumulates labelled value streams and reduces each with a
pluggable `Reduction`, composing across nested loops (the deep-learning
batch → epoch → run pattern). Reductions are *online* — constant memory
per metric, no per-sample storage.

```python
from kaparoo.utils.aggregate import Aggregator, Mean, Last, Max

# One default reduction, plus per-metric overrides:
agg = Aggregator(Mean(), overrides={"lr": Last(), "grad_norm": Max()})
for batch in loader:
    agg.update({"loss": ..., "acc": ..., "lr": ..., "grad_norm": ...},
               weight=len(batch))   # weight = batch size -> correct pooled mean
print(agg.compute())                # {"loss": ..., "acc": ..., "lr": ..., "grad_norm": ...}
```

### Nesting: `merge` vs `update(compute())`

```python
run, history = Aggregator(Mean()), []
for epoch in range(epochs):
    ep = run.fresh()                       # same config, empty
    for batch in loader:
        ep.update(step(batch), weight=len(batch))
    history.append(ep.compute())           # keep per-epoch results
    run.merge(ep)                          # exact pooled mean over ALL batches
print(run.compute())
```

- `merge(child)` combines raw states (same reduction, sample-weighted) —
  the result is exactly as if every batch had fed one tracker.
- `update(child.compute(), weight=...)` feeds a child's *results* back as
  samples, so an outer level can use a **different** reduction than its
  children — e.g. `Aggregator(Min())` fed each epoch's mean to track the
  best epoch.

### Reductions

| Reduction | Result | Empty |
| --- | --- | --- |
| `Mean()` | weighted arithmetic mean | `nan` |
| `Var()` / `Std()` | weighted population variance / std (Welford) | `nan` |
| `Sum()` | sum of values (weight ignored) | `0.0` |
| `Min()` / `Max()` | running min / max (weight ignored) | `nan` |
| `Last()` | most recent value | `nan` |
| `Fold(combine, initial)` | scalar monoid from a callable | `initial` |

Custom reductions extend the family two ways. For a scalar monoid, pass a
callable to `Fold`:

```python
import operator
Aggregator(Fold(operator.mul, 1.0))           # running product
```

For a reduction with richer state (RMS, a weighted geometric mean, ...),
subclass `Reduction` (or `UnweightedReduction` when weight is irrelevant) and
implement `identity` / `step` (or `accumulate`) / `merge` / `result`. The
`merge` method *is* the nesting behavior, so custom reductions nest as
exactly as the built-ins.

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

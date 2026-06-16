# `kaparoo.utils`

Small, focused helpers — not enough material for their own packages.

## Modules

- [`timer`](./timer.py) — `Timer`, `SpanTimer`, `SpanRecord`
- [`aggregate`](./aggregate.py) — `Aggregator` + the `Reduction` family
  (`Mean`, `Var`, `Std`, `Sum`, `Min`, `Max`, `Last`, `Fold`; store-all
  `Stored`, `Median`, `Quantile`; bases `Reduction` / `UnweightedReduction` /
  `OptionalFold`)
- [`optional`](./optional.py) — helpers for `T | None` values
- [`checks`](./checks.py) — `ensure_one_of`, `ensure_in_range`

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

## SpanTimer

`SpanTimer` extends `Timer` — it measures the same total `elapsed` and
adds named time *spans*. Each span
is a `SpanRecord` (a `TypedDict` with `label`, `duration`,
`total_time`) and is produced in one of two ways:

- **`lap(label)` — split.** Each lap's `duration` is the time since the
  previous lap (or the start), so every instant belongs to exactly one
  span.
- **`measure(label)` — stopwatch.** Times only the wrapped block; time
  spent outside any `measure` block is attributed to no span.

```python
from kaparoo.utils.timer import SpanTimer

with SpanTimer("ms", ndigits=1) as st:
    step_a()
    st.lap("A")               # split: time since start
    idle()                    # NOT counted by the next measure
    with st.measure("B"):     # stopwatch: only this block
        step_b()

# Per-span details (`records` is a read-only tuple snapshot):
for record in st.records:
    print(record["label"], record["duration"])

# Aggregated by label (sums `duration` for repeated labels):
print(st.summary)   # e.g. {"A": 12.3, "B": 8.7}
print(st.elapsed)   # total wall time of the `with` block
```

### `lap` vs `measure`

`lap` splits the timeline into contiguous spans — the gap before a
lap is folded into that lap. `measure` brackets a region and ignores
everything outside it, so untimed work between blocks is excluded from
`summary`. Pick `lap` for back-to-back phases, `measure` for discrete
operations interleaved with untimed work. Pauses inside either are
excluded; a `measure` block that raises records nothing.

`measure` doubles as a decorator (every decorated call records one
span, as long as the timer is running when it is called):

```python
st = SpanTimer("ms")

@st.measure("load")
def load() -> None: ...

with st:
    load()        # records a "load" span each call
```

### Same-label policies

| `on_same_label` | Behavior on a repeated label |
| --- | --- |
| `"merge"` *(default)* | record as-is; `summary` aggregates the duplicates |
| `"separate"` | append a `" (N)"` suffix to keep records distinct |
| `"reject"` | raise `ValueError` |

The policy applies to both `lap` and `measure`:

```python
with SpanTimer(on_same_label="separate") as st:
    st.lap("A")
    st.lap("A")   # recorded as "A (2)"
    st.lap("A")   # recorded as "A (3)"
```

## Aggregation

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

### Values are scalars

`update` takes plain numbers, not arrays or tensors. Reduce a batch metric to
a Python `float` at the boundary and weight by the batch size:

```python
agg.update({"loss": loss.detach().item()}, weight=x.size(0))  # PyTorch
agg.update({"loss": float(batch.mean())}, weight=len(batch))  # NumPy
```

Arithmetic reductions like `Mean` / `Sum` happen to accumulate NumPy arrays
element-wise, but `Min` / `Max` / `Median` / `Quantile` raise on them and
`weight` must stay scalar — so converting up front is the reliable path.

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
| `Median()` / `Quantile(q)` | weighted median / `q`-quantile (store-all) | `nan` |
| `Stored(reduce)` | apply `reduce` to all gathered `(value, weight)` pairs | `nan` |

`Median` / `Quantile` / `Stored` are **store-all** reductions for statistics
no online fold can express -- they keep every sample (O(n) memory) instead of
a constant-size state, so use them only when a decomposable reduction cannot.

Custom reductions extend the family two ways. For a scalar monoid, pass a
callable to `Fold`:

```python
import operator
Aggregator(Fold(operator.mul, 1.0))           # running product
```

For a reduction with richer state (RMS, a weighted geometric mean, ...),
subclass `Reduction` (or `UnweightedReduction` when weight is irrelevant) and
implement `identity` / `step` (or `accumulate`) / `merge` / `result`. The
`merge` method *is* the nesting behavior, so custom reductions nest exactly as
the built-ins do — e.g. a weighted geometric mean:

```python
import math

from kaparoo.utils.aggregate import Reduction


class GeoMean(Reduction[tuple[float, float]]):
    def identity(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def step(self, s: tuple[float, float], v: float, w: float) -> tuple[float, float]:
        return (s[0] + w * math.log(v), s[1] + w)

    def merge(
        self, a: tuple[float, float], b: tuple[float, float]
    ) -> tuple[float, float]:
        return (a[0] + b[0], a[1] + b[1])

    def result(self, s: tuple[float, float]) -> float:
        return math.exp(s[0] / s[1]) if s[1] else float("nan")
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

## Checks

Validation guards that return the value (so they compose into an assignment)
or raise a `ValueError` with a consistent message. `name` labels the value in
that message and defaults to `"value"`.

`ensure_one_of` checks discrete membership; pass a `range` for an integer grid.

```python
from kaparoo.utils.checks import ensure_one_of

unit = ensure_one_of(unit, ("s", "ms", "us", "ns"), name="unit")
ensure_one_of(index, range(0, 10, 2), name="index")  # one of 0, 2, 4, 6, 8
```

`ensure_in_range` checks `int` / `float` bounds. Either side may be omitted
for a half-open range; `inclusive` is a single `bool` (both sides) or a
`(lower, upper)` pair; an optional `step` confines the value to a
`base + k*step` grid (anchored at `lower`, else `0`).

```python
from kaparoo.utils.checks import ensure_in_range

ensure_in_range(q, lower=0.0, upper=1.0, name="q")             # closed [0.0, 1.0]
ensure_in_range(w, lower=0.0, inclusive=(False, True), name="w")  # (0.0, inf): w > 0
ensure_in_range(n, lower=0, upper=10, step=2, name="n")        # 0, 2, ..., 10
```

## See also

`kaparoo.utils` underpins the rest of the package rather than depending on a
particular module; the other top-level modules:

- [`kaparoo.filesystem`](../filesystem/) — path helpers, traversal, and
  directory-tree specs
- [`kaparoo.filters`](../filters/) — the string-matching filter DSL
- [`kaparoo.data`](../data/) — lazy, composable data sequences

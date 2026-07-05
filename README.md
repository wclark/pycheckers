# pycheckers

`pycheckers` is a small Python package for checkers move generation and
quiet-position tablebase exploration.

The first implementation is deliberately simple:

- board states are packed integer keys;
- internal graph storage uses Python `dict` and `set`;
- quiet transitions are stored as `source_state_key -> set(target_state_key)`;
- low-cardinality transition metadata is split into separate maps;
- DataFrame views are generated on demand for analysis notebooks.

## Current Scope

The general rules module supports American checkers move generation:

- mandatory capture;
- multi-jump capture turns;
- kings moving and jumping backward;
- promotion;
- the rule that a man stops when crowned during a jump.

The quiet tablebase layer currently focuses on man-only, fixed-piece-count
states. It expands non-capturing, non-promoting moves and records transition
boundaries separately:

- `quiet`: legal quiet successors that stay inside the current tablebase;
- `forced_capture`: capture successors, where forced capture is a property of
  the predecessor state;
- `promotion`: non-capture moves whose successor has a newly crowned king;
- `forced_capture+promotion`: capture moves whose successor promotes.

## Local Development

From this repository root:

```powershell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
```

## Repository Layout

The package code is under `src/pycheckers`. Tests live under `tests`.
Notebook material is intentionally secondary and lives under `notebooks`; those
files are for validating and demonstrating the library during development, not
for driving the package API.

Without installing, tests and notebooks can use the source tree directly by
putting `src` on `PYTHONPATH`.

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

## Minimal Example

```python
from pycheckers import (
    FORCED_CAPTURE,
    QUIET,
    QuietTablebase,
    initial_position,
    inspect_game_state,
)

info = inspect_game_state(initial_position())
print(len(info["metadata_successors"][QUIET]))

tablebase = QuietTablebase().run(max_rounds=3)
print(tablebase.summary())

forced_capture_edges = tablebase.transition_map(3, FORCED_CAPTURE)
print(sum(len(targets) for targets in forced_capture_edges.values()))
```

## Important Data Structures

`QuietTablebase.turn_metadata_maps` is the core round-indexed structure:

```python
[
    {
        "quiet": {source_key: {target_key, ...}},
        "forced_capture": {source_key: {target_key, ...}},
        "promotion": {source_key: {target_key, ...}},
        "forced_capture+promotion": {source_key: {target_key, ...}},
    },
    ...
]
```

Use `transition_map(round_number, metadata)` for a single map, and
`metadata_maps_df()`, `states_df()`, `transitions_df()`, `boundary_edges_df()`,
and `tablebase_summary_df()` for analysis-ready views.

# pycheckers

`pycheckers` is a small Python package for representing checkers board states,
applying American checkers rules, and validating those rules visually in
notebooks.

The package is currently focused on a simple, inspectable core:

- immutable `BoardState` objects;
- black, white, and king bitboards plus side to move;
- 170 side-independent primitive diagonal move templates;
- legal move and legal turn generation;
- mandatory capture;
- multi-jump capture turns;
- kings moving and jumping backward;
- promotion;
- the rule that a man stops when crowned during a jump;
- notebook-friendly move tables and board visualizations.

## Local Development

From this repository root:

```powershell
python -m pip install -e ".[dev]"
python -m compileall -q src tests scripts
ruff check src tests scripts
ruff format --check src tests scripts
pytest --cov=pycheckers --cov-report=term-missing
```

## Repository Layout

The package code is under `src/pycheckers`. Tests live under `tests`.
Notebook material lives under `notebooks`; the main notebook is
`notebooks/primitive_move_catalog.ipynb`.

Development-only exploration notebooks and helpers live under `notebooks/dev`.

Without installing, tests and notebooks can use the source tree directly by
putting `src` on `PYTHONPATH`.

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

The CI path uses `pytest` with coverage reporting and `ruff` for lint and
format checks. Coverage is gated at 82%, just below the current 82.68% baseline,
so the floor can be ratcheted toward full line coverage.

## Minimal Example

```python
from pycheckers import (
    BoardState,
    moves_df,
    primitive_rule_runtime_catalog_df,
    show_primitive_rule_rows,
    show_state,
    show_turn,
)

runtime_rules = primitive_rule_runtime_catalog_df()
print(len(runtime_rules))
show_primitive_rule_rows(runtime_rules.iloc[:3])

state = BoardState.initial()
show_state(state)

moves = state.legal_moves()
print(moves_df(state))

turn = state.legal_turns()[0]
next_state = state.apply_turn(turn)
show_turn(state, turn)
print(next_state)
```

## Board State

`BoardState` stores:

- `black`: a 64-bit mask of black pieces;
- `white`: a 64-bit mask of white pieces;
- `kings`: a 64-bit mask of crowned pieces;
- `side`: `"B"` or `"W"` for side to move.

Construction validates that pieces do not overlap, pieces sit only on playable
dark squares, king bits are a subset of occupied squares, and the side is valid.

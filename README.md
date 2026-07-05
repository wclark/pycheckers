# pycheckers

`pycheckers` is a small Python package for representing American checkers
boards, turns, primitive rules, and rulesets using native 32-bit playable-square
masks.

The package is currently focused on a clean inspectable core:

- `Board`: black, white, and king 32-bit masks;
- `Turn`: a `Board`, side to move, and optional metadata;
- `Conditions`: masks and flags a rule checks against a turn;
- `Effects`: masks and flags a rule applies;
- `Rule`: one primitive move rule;
- `Ruleset`: a collection of rules with native tuple, dict, and set views;
- notebook-friendly board and rule visualizations.

## Local Development

From this repository root:

```powershell
python -m pip install -e ".[dev]"
python -m compileall -q src tests scripts
ruff check src tests scripts
ruff format --check src tests scripts
pytest --cov=pycheckers --cov-report=term-missing
mkdocs build --strict
```

The CI path uses `pytest` with coverage reporting and `ruff` for lint and
format checks. API docs are built with MkDocs and mkdocstrings.

## Minimal Example

```python
from pycheckers import Ruleset, Turn, show_board

ruleset = Ruleset.american()
turn = Turn.initial()

rules = ruleset.to_dataframe()
moves = ruleset.legal_moves(turn)
successors = ruleset.successors(turn)

print(len(rules), len(moves), len(successors))
show_board(turn)
ruleset.plot([0, 1, 2])
```

## Native Data

The core classes expose Python-native structures for analysis and tablebase
experiments:

```python
board_key = turn.board.key
turn_record = turn.as_dict()
rule_records = ruleset.records
rule_index = ruleset.record_map[0]
rule_keys = ruleset.rule_set
by_side = ruleset.rules_by_side
by_metadata = ruleset.rules_by_metadata
```

All masks are 32-bit playable-square masks. There is no 64-bit board conversion
layer in the public API.

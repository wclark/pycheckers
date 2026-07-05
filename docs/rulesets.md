# Rulesets

The default ruleset is `Ruleset.american()`. It stores one row per primitive
runtime rule. Each row contains six 32-bit playable-square masks:

- `is_black`
- `is_white`
- `is_empty`
- `be_black`
- `be_white`
- `be_empty`

It also stores four one-bit rule flags:

- `black_to_move`
- `king`
- `promotion`
- `capture`

The dataframe and plotting views are methods on the ruleset:

```python
from pycheckers import Ruleset

ruleset = Ruleset.american()
df = ruleset.to_dataframe()
figures = ruleset.plot(df.iloc[:3])
```

Legal primitive rules can be found against either `BoardState` or `TurnState`:

```python
from pycheckers import BoardState, Ruleset, TurnState

ruleset = Ruleset.american()
board = BoardState.initial()
turn = TurnState.from_board_state(board)

rule_indexes = ruleset.legal_rule_indices(turn)
moves = ruleset.legal_moves(board)
next_states = ruleset.successors(turn)
```

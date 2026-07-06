# Rulesets

The default ruleset is `Ruleset.american()`. It stores one row per primitive
runtime rule. Each row has conditions, effects, and metadata:

- conditions: `is_black`, `is_white`, `is_empty`, `black_to_move`, `king`;
- effects: `be_black`, `be_white`, `be_empty`, `promotion`, `capture`.

The ruleset exposes native Python views for analysis:

```python
from pycheckers import Ruleset

ruleset = Ruleset.american()

records = ruleset.records
record_map = ruleset.record_map
rule_keys = ruleset.rule_set
by_side = ruleset.rules_by_side
by_metadata = ruleset.rules_by_metadata
```

It also provides dataframe and graphical display views:

```python
df = ruleset.to_dataframe()
figures = ruleset.display(df.iloc[:3])
```

Legal primitive rules are matched against `Turn` objects:

```python
from pycheckers import Ruleset, Turn

ruleset = Ruleset.american()
turn = Turn.initial()

rule_indexes = ruleset.legal_rule_indices(turn)
rules = ruleset.legal_rules(turn)
moves = ruleset.legal_moves(turn)
next_turns = ruleset.successors(turn)
next_by_rule = ruleset.successor_map(turn)
```

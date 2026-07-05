# pycheckers

`pycheckers` is a small Python package for American checkers board states,
primitive rule tables, legal move generation, and notebook-friendly inspection.

The core public objects are:

- `BoardState`, the 8x8 board representation used by the package API.
- `TurnState`, a compact 32-bit playable-square representation for fast rule matching.
- `Ruleset`, the compact primitive-rule table used to generate legal primitive moves.

The package is still pre-alpha. The current development target is a clean,
well-tested rules layer that can later support larger tablebase work.

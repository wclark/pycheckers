# pycheckers

`pycheckers` is a compact native-32-bit model for American checkers boards,
turns, primitive rules, and rulesets.

The core public objects are:

- `Board`, a tuple-like set of black, white, and king masks.
- `Turn`, a `Board` plus side-to-move and optional metadata.
- `Conditions` and `Effects`, the two halves of a primitive rule.
- `Rule`, one condition/effect transformation.
- `Ruleset`, the generated American checkers primitive-rule table.

The package is still pre-alpha. The current development target is a clean,
well-tested rules layer that can later support larger tablebase work.

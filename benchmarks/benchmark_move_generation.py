"""Small repeatable baseline for Clatsop's pure-Python move generator."""

from __future__ import annotations

import argparse
import json
from time import perf_counter

from clatsop import Ruleset, Turn, square_mask32


def benchmark(iterations: int) -> dict[str, float | int]:
    ruleset = Ruleset.american()
    turns = (
        Turn.initial(),
        Turn.from_masks(square_mask32(2, 1), square_mask32(3, 2), 0, 1),
        Turn.from_masks(
            square_mask32(2, 1),
            square_mask32(3, 2) | square_mask32(5, 4),
            0,
            1,
        ),
    )

    started = perf_counter()
    transitions = 0
    for _ in range(iterations):
        for turn in turns:
            transitions += len(ruleset.legal_transitions(turn))
    seconds = perf_counter() - started
    positions = iterations * len(turns)
    return {
        "iterations": iterations,
        "positions": positions,
        "transitions": transitions,
        "seconds": seconds,
        "positions_per_second": positions / seconds,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10_000)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.iterations), indent=2))


if __name__ == "__main__":
    main()

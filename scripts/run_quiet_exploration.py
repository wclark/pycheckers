import argparse
import csv
import json
import time
from pathlib import Path

from pycheckers.quiet import QuietPositionGraph, ROUND_METRIC_FIELDS


METRIC_FIELDS = ROUND_METRIC_FIELDS


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Expand reachable 12-vs-12 non-king checkers states by quiet moves "
            "and log per-round growth metrics."
        )
    )
    parser.add_argument("--max-rounds", type=int, default=None)
    parser.add_argument("--max-seconds", type=float, default=None)
    parser.add_argument("--max-total-states", type=int, default=None)
    parser.add_argument("--out-dir", default="quiet_exploration_runs")
    parser.add_argument("--run-name", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    run_name = args.run_name or time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out_dir) / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "round_metrics.csv"
    jsonl_path = out_dir / "round_metrics.jsonl"

    graph = QuietPositionGraph()
    started = time.perf_counter()

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file, jsonl_path.open(
        "w", encoding="utf-8"
    ) as jsonl_file:
        writer = csv.DictWriter(csv_file, fieldnames=METRIC_FIELDS)
        writer.writeheader()

        print(
            "round elapsed round_sec frontier processed new total next_frontier "
            "pruned_states pruned_moves terminal_total states_per_sec",
            flush=True,
        )

        while graph.frontier_keys:
            if args.max_rounds is not None and len(graph.rounds) >= args.max_rounds:
                break
            if args.max_seconds is not None and time.perf_counter() - started >= args.max_seconds:
                break
            if args.max_total_states is not None and len(graph.state_keys) >= args.max_total_states:
                break

            row = graph.run_round(started=started)

            writer.writerow(row)
            csv_file.flush()
            jsonl_file.write(json.dumps(row, sort_keys=True) + "\n")
            jsonl_file.flush()

            print(
                f"{row['round']:>5} {row['elapsed_sec']:>9.3f} {row['round_sec']:>9.3f} "
                f"{row['frontier_in']:>8} {row['processed']:>9} {row['new_states']:>8} "
                f"{row['total_states']:>9} {row['next_frontier']:>13} "
                f"{row['pruned_leaf_states']:>13} {row['pruned_leaf_moves']:>12} "
                f"{row['terminal_states_total']:>14} {row['states_per_sec']:>14}",
                flush=True,
            )

    print(f"metrics_csv={csv_path.resolve()}", flush=True)
    print(f"metrics_jsonl={jsonl_path.resolve()}", flush=True)
    print(
        f"stopped_after_rounds={len(graph.rounds)} total_states={len(graph.state_keys)} "
        f"frontier={len(graph.frontier_keys)} expanded={len(graph.expanded_keys)} "
        f"pruned_leaf_states_total={len(graph.boundary_state_info)} "
        f"terminal_states_total={len(graph.terminal_keys)}",
        flush=True,
    )


if __name__ == "__main__":
    main()

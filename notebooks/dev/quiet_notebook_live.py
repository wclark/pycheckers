import csv
import heapq
import json
import time
from pathlib import Path

from pycheckers import (
    expand_quiet_man_states,
    initial_position,
    is_dark,
    legal_moves,
    show_board,
    square_from_mask,
    square_mask,
)
from pycheckers.quiet import QuietPositionGraph, ROUND_METRIC_FIELDS, square64_to32


def run_live_quiet_exploration(
    max_rounds=None,
    max_seconds=120,
    max_total_states=3_000_000,
    out_dir="quiet_exploration_runs",
    run_name=None,
    pause_sec=0.05,
):
    """Run quiet-state exploration with a live-updating notebook chart."""
    import matplotlib.pyplot as plt
    from IPython.display import HTML, display

    run_name = run_name or time.strftime("notebook-%Y%m%d-%H%M%S")
    out_path = Path(out_dir) / run_name
    out_path.mkdir(parents=True, exist_ok=True)
    csv_path = out_path / "round_metrics.csv"
    jsonl_path = out_path / "round_metrics.jsonl"

    graph = QuietPositionGraph()
    graph.csv_path = csv_path
    graph.jsonl_path = jsonl_path
    started = time.perf_counter()

    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    fig.suptitle("Quiet 12-vs-12 non-king exploration")
    chart_handle = display(fig, display_id=True)
    plt.close(fig)
    status_handle = display(HTML(_status_html([], csv_path, jsonl_path, True)), display_id=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file, jsonl_path.open(
        "w", encoding="utf-8"
    ) as jsonl_file:
        writer = csv.DictWriter(csv_file, fieldnames=ROUND_METRIC_FIELDS)
        writer.writeheader()
        stop_reason = "frontier exhausted"

        while graph.frontier_keys:
            elapsed = time.perf_counter() - started
            if max_rounds is not None and len(graph.rounds) >= max_rounds:
                stop_reason = "max rounds reached"
                break
            if max_seconds is not None and elapsed >= max_seconds:
                stop_reason = "max seconds reached"
                break
            if max_total_states is not None and len(graph.state_keys) >= max_total_states:
                stop_reason = "max total states reached"
                break

            row = graph.run_round(started=started)
            writer.writerow(row)
            csv_file.flush()
            jsonl_file.write(json.dumps(row, sort_keys=True) + "\n")
            jsonl_file.flush()

            _draw_progress(fig, axes, graph.rounds)
            _update_display(chart_handle, fig)
            _update_display(status_handle, HTML(_status_html(graph.rounds, csv_path, jsonl_path, True)))
            if pause_sec:
                plt.pause(pause_sec)

    graph.stop_reason = stop_reason
    _draw_progress(fig, axes, graph.rounds)
    _update_display(chart_handle, fig)
    _update_display(
        status_handle,
        HTML(_status_html(graph.rounds, csv_path, jsonl_path, False, stop_reason)),
    )

    return graph


class QuietExplorationArtifact:
    def __init__(
        self,
        states,
        frontier,
        expanded,
        boundary_states,
        terminal_states,
        transitions,
        parents,
        predecessors,
        rows,
        csv_path,
        jsonl_path,
        stop_reason,
    ):
        self.states = states
        self.frontier = frontier
        self.expanded = expanded
        self.boundary_states = boundary_states
        self.terminal_states = terminal_states
        self.transitions = transitions
        self.parents = parents
        self.predecessors = predecessors
        self.rows = rows
        self.csv_path = csv_path
        self.jsonl_path = jsonl_path
        self.stop_reason = stop_reason
        self._terminal_list = None
        self._boundary_list = None
        self._path_count_memo = {}

    def __getitem__(self, key):
        return getattr(self, key)

    def summary(self):
        latest = self.rows[-1] if self.rows else {}
        return {
            "stop_reason": self.stop_reason,
            "rounds": len(self.rows),
            "total_states": len(self.states),
            "frontier": len(self.frontier),
            "expanded": len(self.expanded),
            "transitions": len(self.transitions),
            "pruned_boundary_states": len(self.boundary_states),
            "terminal_states": len(self.terminal_states),
            "latest_round": latest,
            "csv_path": str(self.csv_path),
            "jsonl_path": str(self.jsonl_path),
        }

    @property
    def terminal_count(self):
        return len(self.terminal_states)

    @property
    def boundary_count(self):
        return len(self.boundary_states)

    @property
    def transition_count(self):
        return len(self.transitions)

    def terminal_list(self):
        if self._terminal_list is None:
            self._terminal_list = sorted(self.terminal_states, key=_state_sort_key)
        return self._terminal_list

    def boundary_list(self):
        if self._boundary_list is None:
            self._boundary_list = sorted(self.boundary_states, key=_state_sort_key)
        return self._boundary_list

    def terminal_state(self, index=0):
        terminals = self.terminal_list()
        if not terminals:
            raise IndexError("this run has no terminal states")
        return terminals[index]

    def boundary_state(self, index=0):
        boundaries = self.boundary_list()
        if not boundaries:
            raise IndexError("this run has no pruned boundary states")
        return boundaries[index]

    def path_to_state(self, state):
        if state not in self.states:
            raise KeyError("state is not in this artifact's distinct-state set")

        path = []
        seen = set()
        current = state
        while True:
            if current in seen:
                raise ValueError("cycle found in parent map")
            seen.add(current)
            path.append(current)
            parent = self.parents.get(current)
            if parent is None:
                break
            current, _move = parent
        path.reverse()
        return path

    def predecessor_links(self, state):
        if state not in self.states:
            raise KeyError("state is not in this artifact's distinct-state set")
        return list(self.predecessors.get(state, []))

    def path_count_to_state(self, state):
        if state not in self.states:
            raise KeyError("state is not in this artifact's distinct-state set")
        return self._path_count_to_state(state, self._path_count_memo)

    def path_counts(self, refresh=False, progress_every=0):
        return compute_path_counts(
            self,
            refresh=refresh,
            progress_every=progress_every,
        )

    def path_count_distribution_df(
        self,
        which="all",
        max_path_count=10,
        refresh=False,
        progress_every=0,
    ):
        return path_count_distribution_df(
            self,
            which=which,
            max_path_count=max_path_count,
            refresh=refresh,
            progress_every=progress_every,
        )

    def least_path_count_states_df(
        self,
        which="all",
        limit=50,
        max_path_count=None,
        include_flags=True,
        include_tuple=False,
        refresh=False,
        progress_every=0,
    ):
        return least_path_count_states_df(
            self,
            which=which,
            limit=limit,
            max_path_count=max_path_count,
            include_flags=include_flags,
            include_tuple=include_tuple,
            refresh=refresh,
            progress_every=progress_every,
        )

    def unique_path_states_df(
        self,
        which="all",
        limit=50,
        include_flags=True,
        include_tuple=False,
        refresh=False,
        progress_every=0,
    ):
        return unique_path_states_df(
            self,
            which=which,
            limit=limit,
            include_flags=include_flags,
            include_tuple=include_tuple,
            refresh=refresh,
            progress_every=progress_every,
        )

    def _path_count_to_state(self, state, memo):
        if state in memo:
            return memo[state]
        links = self.predecessors.get(state, [])
        if not links:
            memo[state] = 1
        else:
            memo[state] = sum(self._path_count_to_state(prev, memo) for prev, _move in links)
        return memo[state]

    def path_edges_to_state(self, state):
        path = self.path_to_state(state)
        edges = []
        for next_state in path[1:]:
            previous_state, move = self.parents[next_state]
            edges.append((previous_state, move, next_state))
        return edges

    def path_to_terminal(self, index=0):
        return self.path_to_state(self.terminal_state(index))

    def path_count_to_terminal(self, index=0):
        return self.path_count_to_state(self.terminal_state(index))

    def path_edges_to_terminal(self, index=0):
        return self.path_edges_to_state(self.terminal_state(index))

    def path_table_to_state(self, state):
        return _path_table(self.path_edges_to_state(state))

    def path_table_to_terminal(self, index=0):
        return self.path_table_to_state(self.terminal_state(index))

    def iter_paths_to_state(self, state, max_paths=None):
        if state not in self.states:
            raise KeyError("state is not in this artifact's distinct-state set")
        yielded = 0

        def walk(current):
            nonlocal yielded
            if max_paths is not None and yielded >= max_paths:
                return
            links = self.predecessors.get(current, [])
            if not links:
                yielded += 1
                yield [current]
                return
            for prev, _move in links:
                for path in walk(prev):
                    if max_paths is not None and yielded > max_paths:
                        return
                    yield path + [current]

        yield from walk(state)

    def iter_paths_to_terminal(self, index=0, max_paths=None):
        yield from self.iter_paths_to_state(self.terminal_state(index), max_paths=max_paths)

    def all_paths_to_state(self, state, max_paths=None):
        return list(self.iter_paths_to_state(state, max_paths=max_paths))

    def all_paths_to_terminal(self, index=0, max_paths=None):
        return list(self.iter_paths_to_terminal(index=index, max_paths=max_paths))

    def path_edges(self, path):
        edges = []
        for prev, next_state in zip(path, path[1:]):
            move = None
            for candidate_prev, candidate_move in self.predecessors.get(next_state, []):
                if candidate_prev == prev:
                    move = candidate_move
                    break
            if move is None:
                raise ValueError("path contains states without a recorded transition")
            edges.append((prev, move, next_state))
        return edges

    def all_path_tables_to_terminal(self, index=0, max_paths=None):
        rows = []
        for path_index, path in enumerate(
            self.iter_paths_to_terminal(index=index, max_paths=max_paths)
        ):
            rows.extend(_path_rows(self.path_edges(path), path_index=path_index))
        return _html_table(rows, title="all terminal paths")

    def show_state(self, state, dots=0, size=1.5):
        black, white, kings, side = state
        fig, axes = show_board(black, white, kings, dots=dots, size=size)
        fig.suptitle(f"side to move: {side}")
        return fig, axes

    def show_terminal(self, index=0, size=1.5):
        return self.show_state(self.terminal_state(index), size=size)

    def show_path_to_state(self, state, max_boards=16, size=1.6, tail=True):
        return _show_state_path(self.path_to_state(state), max_boards=max_boards, size=size, tail=tail)

    def show_path_to_terminal(self, index=0, max_boards=16, size=1.6, tail=True):
        return self.show_path_to_state(
            self.terminal_state(index),
            max_boards=max_boards,
            size=size,
            tail=tail,
        )

    def show_all_paths_to_terminal(
        self,
        index=0,
        max_paths=None,
        max_boards_per_path=16,
        size=1.4,
        tail=True,
    ):
        paths = self.all_paths_to_terminal(index=index, max_paths=max_paths)
        return _show_many_state_paths(
            paths,
            max_boards_per_path=max_boards_per_path,
            size=size,
            tail=tail,
        )

    def show_boundary(self, index=0, size=2, show_legal_destinations=True):
        state = self.boundary_state(index)
        dots = 0
        if show_legal_destinations:
            black, white, kings, side = state
            for move in legal_moves(black, white, kings, side):
                dots |= move["to_mask"]
        return self.show_state(state, dots=dots, size=size)

    def terminal_table(self, limit=20, start=0):
        rows = []
        for index, state in enumerate(self.terminal_list()[start : start + limit], start=start):
            rows.append(
                _state_row(
                    index,
                    state,
                    extra={
                        "first_path_len": len(self.path_to_state(state)) - 1,
                        "path_count": self.path_count_to_state(state),
                        "predecessors": len(self.predecessors.get(state, [])),
                    },
                )
            )
        return _html_table(rows, title="terminal")

    def boundary_table(self, limit=20, start=0):
        states = self.boundary_list()
        rows = []
        for index, state in enumerate(states[start : start + limit], start=start):
            info = self.boundary_states[state]
            rows.append(
                _state_row(
                    index,
                    state,
                    extra={
                        "first_path_len": len(self.path_to_state(state)) - 1,
                        "path_count": self.path_count_to_state(state),
                        "predecessors": len(self.predecessors.get(state, [])),
                        "capture": info.get("capture", 0),
                        "promotion": info.get("promotion", 0),
                        "capture+promotion": info.get("capture+promotion", 0),
                    },
                )
            )
        return _html_table(rows, title="boundary")

    def metrics_df(self):
        return _dataframe(self.rows)

    def states_df(
        self,
        which="all",
        sort=False,
        include_flags=True,
        include_path_counts=False,
        include_tuple=False,
    ):
        states = self._select_states(which)
        if sort:
            states = sorted(states, key=_state_sort_key)

        rows = []
        for index, state in enumerate(states):
            row = {"index": index}
            row.update(
                _state_record(
                    state,
                    include_tuple=include_tuple,
                )
            )
            if include_flags:
                row.update(
                    {
                        "in_frontier": state in self.frontier,
                        "expanded": state in self.expanded,
                        "is_terminal": state in self.terminal_states,
                        "is_boundary": state in self.boundary_states,
                        "predecessors": len(self.predecessors.get(state, [])),
                    }
                )
            if include_path_counts:
                row["path_count"] = self.path_count_to_state(state)
            rows.append(row)
        return _dataframe(rows)

    def terminal_states_df(
        self,
        sort=True,
        include_path_counts=True,
        include_tuple=False,
    ):
        return self.states_df(
            which="terminal",
            sort=sort,
            include_flags=True,
            include_path_counts=include_path_counts,
            include_tuple=include_tuple,
        )

    def boundary_states_df(
        self,
        sort=True,
        include_path_counts=False,
        include_tuple=False,
    ):
        states = self._select_states("boundary")
        if sort:
            states = sorted(states, key=_state_sort_key)

        rows = []
        for index, state in enumerate(states):
            info = self.boundary_states[state]
            row = {"index": index}
            row.update(
                _state_record(
                    state,
                    include_tuple=include_tuple,
                )
            )
            row.update(
                {
                    "predecessors": len(self.predecessors.get(state, [])),
                    "capture": info.get("capture", 0),
                    "promotion": info.get("promotion", 0),
                    "capture_promotion": info.get("capture+promotion", 0),
                    "boundary_moves": info.get("moves", 0),
                }
            )
            if include_path_counts:
                row["path_count"] = self.path_count_to_state(state)
            rows.append(row)
        return _dataframe(rows)

    def transitions_df(self, sort=False, include_tuple=False):
        rows = []
        for next_state, links in self.predecessors.items():
            for previous_state, move in links:
                row = {"transition_index": len(rows)}
                row.update(
                    _state_record(
                        previous_state,
                        prefix="prev_",
                        include_tuple=include_tuple,
                    )
                )
                row.update(
                    _state_record(
                        next_state,
                        prefix="next_",
                        include_tuple=include_tuple,
                    )
                )
                row.update(_move_record(move))
                rows.append(row)

        if sort:
            rows.sort(
                key=lambda row: (
                    row["next_side"],
                    row["next_black"],
                    row["next_white"],
                    row["next_kings"],
                    row["prev_side"],
                    row["prev_black"],
                    row["prev_white"],
                    row["prev_kings"],
                )
            )
            for index, row in enumerate(rows):
                row["transition_index"] = index
        return _dataframe(rows)

    def terminal_paths_df(self, index=0, max_paths=None, include_tuple=False):
        return self.paths_df_to_state(
            self.terminal_state(index),
            max_paths=max_paths,
            include_tuple=include_tuple,
        )

    def paths_df_to_state(self, state, max_paths=None, include_tuple=False):
        rows = []
        for path_index, path in enumerate(self.iter_paths_to_state(state, max_paths=max_paths)):
            for step, (previous_state, move, next_state) in enumerate(self.path_edges(path), start=1):
                row = {"path_index": path_index, "step": step}
                row.update(
                    _state_record(
                        previous_state,
                        prefix="prev_",
                        include_tuple=include_tuple,
                    )
                )
                row.update(
                    _state_record(
                        next_state,
                        prefix="next_",
                        include_tuple=include_tuple,
                    )
                )
                row.update(_move_record(move))
                rows.append(row)
        return _dataframe(rows)

    def terminal_path_states_df(
        self,
        index=0,
        max_paths=None,
        include_tuple=False,
    ):
        return self.path_states_df_to_state(
            self.terminal_state(index),
            max_paths=max_paths,
            include_tuple=include_tuple,
        )

    def path_states_df_to_state(
        self,
        state,
        max_paths=None,
        include_tuple=False,
    ):
        rows = []
        for path_index, path in enumerate(self.iter_paths_to_state(state, max_paths=max_paths)):
            final_step = len(path) - 1
            for step, path_state in enumerate(path):
                row = {
                    "path_index": path_index,
                    "step": step,
                    "is_start": step == 0,
                    "is_target": step == final_step,
                }
                row.update(
                    _state_record(
                        path_state,
                        include_tuple=include_tuple,
                    )
                )
                rows.append(row)
        return _dataframe(rows)

    def _select_states(self, which):
        if isinstance(which, str):
            if which == "all":
                return list(self.states)
            if which == "frontier":
                return list(self.frontier)
            if which == "expanded":
                return list(self.expanded)
            if which == "terminal":
                return self.terminal_list()
            if which == "boundary":
                return self.boundary_list()
            raise ValueError(
                "which must be 'all', 'frontier', 'expanded', 'terminal', or 'boundary'"
            )
        return list(which)

    def state_ascii(self, state):
        black, white, kings, side = state
        rows = [f"side: {side}"]
        for r in range(8):
            chars = []
            for c in range(8):
                bit = 1 << (8 * r + c)
                if black & bit:
                    chars.append("B" if kings & bit else "b")
                elif white & bit:
                    chars.append("W" if kings & bit else "w")
                else:
                    chars.append(".")
            rows.append("".join(chars))
        return "\n".join(rows)


def _draw_progress(fig, axes, rows):
    if not rows:
        return

    rounds = [row["round"] for row in rows]
    panels = [
        (
            axes[0][0],
            "Cumulative states",
            [("total_states", "total"), ("expanded_total", "expanded")],
            True,
        ),
        (
            axes[0][1],
            "Round growth",
            [("new_states", "new states"), ("existing_state_targets", "existing-state targets")],
            False,
        ),
        (
            axes[1][0],
            "Pruned exits",
            [
                ("pruned_leaf_states", "pruned source states"),
                ("pruned_leaf_moves", "pruned legal moves"),
            ],
            False,
        ),
        (
            axes[1][1],
            "Terminal states",
            [
                ("terminal_states_total", "terminal total"),
            ],
            False,
        ),
        (
            axes[2][0],
            "Round seconds",
            [("round_sec", "round seconds")],
            False,
        ),
        (
            axes[2][1],
            "Throughput",
            [("states_per_sec", "states/sec")],
            True,
        ),
    ]

    for ax, title, series, log_y in panels:
        ax.clear()
        for key, label in series:
            ax.plot(rounds, [row[key] for row in rows], marker="o", linewidth=1.8, label=label)
        ax.set_title(title)
        ax.set_xlabel("round")
        ax.grid(True, alpha=0.25)
        if log_y:
            ax.set_yscale("log")
        ax.legend(loc="best", fontsize=8)

    latest = rows[-1]
    fig.suptitle(
        "Quiet 12-vs-12 non-king exploration "
        f"- round {latest['round']}, total {latest['total_states']:,}"
    )


def _update_display(handle, value):
    if handle is not None:
        handle.update(value)


def _status_html(rows, csv_path, jsonl_path, running, stop_reason=""):
    status = "running" if running else f"stopped: {stop_reason}"
    if rows:
        latest = rows[-1]
        summary = (
            f"<b>Status:</b> {status}<br>"
            f"<b>Round:</b> {latest['round']} &nbsp; "
            f"<b>Total:</b> {latest['total_states']:,} &nbsp; "
            f"<b>New:</b> {latest['new_states']:,} &nbsp; "
            f"<b>Frontier:</b> {latest['next_frontier']:,}<br>"
            f"<b>Pruned source states:</b> {latest['pruned_leaf_states']:,} &nbsp; "
            f"<b>Pruned moves:</b> {latest['pruned_leaf_moves']:,} &nbsp; "
            f"<b>Terminal total:</b> {latest['terminal_states_total']:,} &nbsp; "
            f"<b>Round seconds:</b> {latest['round_sec']}"
        )
        table = _latest_rows_table(rows[-10:])
    else:
        summary = f"<b>Status:</b> {status}<br>Waiting for the first round..."
        table = ""

    return (
        "<div style='font-family: system-ui, sans-serif; font-size: 13px'>"
        f"{summary}<br><b>CSV:</b> {csv_path}<br><b>JSONL:</b> {jsonl_path}"
        f"{table}</div>"
    )


def _latest_rows_table(rows):
    headers = [
        "round",
        "new_states",
        "total_states",
        "next_frontier",
        "pruned_leaf_states",
        "pruned_leaf_moves",
        "terminal_states_total",
        "round_sec",
        "states_per_sec",
        "new_transitions",
        "total_transitions",
    ]
    header_html = "".join(f"<th>{header}</th>" for header in headers)
    body = []
    for row in reversed(rows):
        cells = []
        for header in headers:
            value = row[header]
            if isinstance(value, int):
                value = f"{value:,}"
            cells.append(f"<td>{value}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")

    return (
        "<table style='border-collapse: collapse; margin-top: 8px'>"
        f"<thead><tr>{header_html}</tr></thead>"
        "<tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def _state_sort_key(state):
    black, white, kings, side = state
    return (side, black, white, kings)


def compute_path_counts(artifact, refresh=False, progress_every=0):
    cached = getattr(artifact, "_all_path_counts", None)
    if (
        cached is not None
        and not refresh
        and len(cached) >= len(artifact.states)
    ):
        return cached

    counts = {} if refresh else getattr(artifact, "_path_count_memo", None)
    if counts is None:
        counts = {}
    if len(counts) >= len(artifact.states):
        artifact._path_count_memo = counts
        artifact._all_path_counts = counts
        return counts

    buckets = {}
    for state in artifact.states:
        buckets.setdefault(_quiet_state_score(state), []).append(state)

    processed = 0
    started = time.perf_counter()
    predecessors = artifact.predecessors
    total = len(artifact.states)
    for score in sorted(buckets):
        for state in buckets[score]:
            if state not in counts:
                links = predecessors.get(state, [])
                if links:
                    counts[state] = sum(
                        _path_count_from_predecessors(prev, predecessors, counts)
                        for prev, _move in links
                    )
                else:
                    counts[state] = 1
            processed += 1
            if progress_every and processed % progress_every == 0:
                elapsed = time.perf_counter() - started
                rate = processed / elapsed if elapsed else 0.0
                print(f"path counts: {processed:,}/{total:,} states ({rate:,.0f}/sec)")

    artifact._path_count_memo = counts
    artifact._all_path_counts = counts
    return counts


def path_count_distribution_df(
    artifact,
    which="all",
    max_path_count=10,
    refresh=False,
    progress_every=0,
):
    counts = compute_path_counts(
        artifact,
        refresh=refresh,
        progress_every=progress_every,
    )
    distribution = {}
    overflow = 0
    selected = _artifact_select_states(artifact, which)

    for state in selected:
        path_count = counts[state]
        if max_path_count is not None and path_count > max_path_count:
            overflow += 1
        else:
            distribution[path_count] = distribution.get(path_count, 0) + 1

    rows = [
        {
            "which": which if isinstance(which, str) else "custom",
            "path_count": path_count,
            "path_count_label": str(path_count),
            "states": state_count,
        }
        for path_count, state_count in sorted(distribution.items())
    ]
    if overflow:
        rows.append(
            {
                "which": which if isinstance(which, str) else "custom",
                "path_count": None,
                "path_count_label": f">{max_path_count}",
                "states": overflow,
            }
        )
    return _dataframe(rows)


def least_path_count_states_df(
    artifact,
    which="all",
    limit=50,
    max_path_count=None,
    include_flags=True,
    include_tuple=False,
    refresh=False,
    progress_every=0,
):
    counts = compute_path_counts(
        artifact,
        refresh=refresh,
        progress_every=progress_every,
    )

    def eligible_states():
        for state in _artifact_select_states(artifact, which):
            path_count = counts[state]
            if max_path_count is None or path_count <= max_path_count:
                yield state

    def sort_key(state):
        return (counts[state], _quiet_state_depth(state), _state_sort_key(state))

    if limit is None:
        selected = sorted(eligible_states(), key=sort_key)
    else:
        selected = heapq.nsmallest(limit, eligible_states(), key=sort_key)

    rows = []
    for state in selected:
        rows.append(
            _path_count_state_record(
                artifact,
                state,
                counts[state],
                include_flags=include_flags,
                include_tuple=include_tuple,
            )
        )
    return _dataframe(rows)


def unique_path_states_df(
    artifact,
    which="all",
    limit=50,
    include_flags=True,
    include_tuple=False,
    refresh=False,
    progress_every=0,
):
    return least_path_count_states_df(
        artifact,
        which=which,
        limit=limit,
        max_path_count=1,
        include_flags=include_flags,
        include_tuple=include_tuple,
        refresh=refresh,
        progress_every=progress_every,
    )


def _path_count_from_predecessors(state, predecessors, counts):
    if state in counts:
        return counts[state]
    links = predecessors.get(state, [])
    if not links:
        counts[state] = 1
    else:
        counts[state] = sum(
            _path_count_from_predecessors(prev, predecessors, counts)
            for prev, _move in links
        )
    return counts[state]


def _artifact_select_states(artifact, which):
    if isinstance(which, str):
        if which == "all":
            return list(artifact.states)
        if which == "frontier":
            return list(artifact.frontier)
        if which == "expanded":
            return list(artifact.expanded)
        if which == "terminal":
            if hasattr(artifact, "terminal_list"):
                return artifact.terminal_list()
            return sorted(artifact.terminal_states, key=_state_sort_key)
        if which == "boundary":
            if hasattr(artifact, "boundary_list"):
                return artifact.boundary_list()
            return sorted(artifact.boundary_states, key=_state_sort_key)
        raise ValueError(
            "which must be 'all', 'frontier', 'expanded', 'terminal', or 'boundary'"
        )
    return list(which)


def _path_count_state_record(
    artifact,
    state,
    path_count,
    include_flags=True,
    include_tuple=False,
):
    row = {
        "path_count": path_count,
        "quiet_depth": _quiet_state_depth(state),
        "first_path_len": _first_path_len(artifact, state),
        "predecessors": len(artifact.predecessors.get(state, [])),
    }
    row.update(
        _state_record(
            state,
            include_tuple=include_tuple,
        )
    )
    if include_flags:
        row.update(
            {
                "in_frontier": state in artifact.frontier,
                "expanded": state in artifact.expanded,
                "is_terminal": state in artifact.terminal_states,
                "is_boundary": state in artifact.boundary_states,
            }
        )
    if state in artifact.boundary_states:
        info = artifact.boundary_states[state]
        row.update(
            {
                "capture": info.get("capture", 0),
                "promotion": info.get("promotion", 0),
                "capture_promotion": info.get("capture+promotion", 0),
                "boundary_moves": info.get("moves", 0),
            }
        )
    return row


def _first_path_len(artifact, state):
    if hasattr(artifact, "path_to_state"):
        return len(artifact.path_to_state(state)) - 1

    length = 0
    current = state
    seen = set()
    while True:
        if current in seen:
            raise ValueError("cycle found in parent map")
        seen.add(current)
        parent = artifact.parents.get(current)
        if parent is None:
            return length
        current, _move = parent
        length += 1


def _quiet_state_score(state):
    black, white, _kings, _side = state
    return _mask_row_sum(black) - _mask_row_sum(white)


def _quiet_state_depth(state):
    return _quiet_state_score(state) - _initial_quiet_state_score()


def _initial_quiet_state_score():
    score = getattr(_initial_quiet_state_score, "_score", None)
    if score is None:
        black, white, _kings, _side = initial_position()
        score = _mask_row_sum(black) - _mask_row_sum(white)
        _initial_quiet_state_score._score = score
    return score


def _mask_row_sum(mask):
    total = 0
    for row in range(8):
        total += row * ((mask >> (8 * row)) & 0xFF).bit_count()
    return total


def _state_row(index, state, extra=None):
    black, white, kings, side = state
    row = {
        "index": index,
        "side": side,
        "black_hex": hex(black),
        "white_hex": hex(white),
        "kings_hex": hex(kings),
        "black_count": black.bit_count(),
        "white_count": white.bit_count(),
    }
    if extra:
        row.update(extra)
    return row


def _dataframe(rows):
    import pandas as pd

    return pd.DataFrame.from_records(rows)


def _state_record(state, prefix="", include_tuple=False):
    black, white, kings, side = state
    row = {
        f"{prefix}black": black,
        f"{prefix}white": white,
        f"{prefix}kings": kings,
        f"{prefix}side": side,
    }
    if include_tuple:
        row[f"{prefix}state"] = state
    return row


def _move_record(move):
    from_r, from_c = square_from_mask(move["from_mask"])
    to_r, to_c = square_from_mask(move["to_mask"])
    captured_mask = move.get("captured_mask", 0)
    from_square = square64_to32(move["from_mask"])
    to_square = square64_to32(move["to_mask"])
    if captured_mask:
        captured_r, captured_c = square_from_mask(captured_mask)
        captured_square = square64_to32(captured_mask)
    else:
        captured_r = captured_c = None
        captured_square = None

    return {
        "from_square": from_square,
        "to_square": to_square,
        "captured_square": captured_square,
        "from_r": from_r,
        "from_c": from_c,
        "to_r": to_r,
        "to_c": to_c,
        "captured_r": captured_r,
        "captured_c": captured_c,
        "dr": move["dr"],
        "dc": move["dc"],
        "is_capture": bool(move.get("is_capture")),
    }


def _state_table(states, limit=20, start=0, title="state"):
    rows = [
        _state_row(index, state)
        for index, state in enumerate(states[start : start + limit], start=start)
    ]
    return _html_table(rows, title=title)


def _path_table(edges):
    return _html_table(_path_rows(edges), title="path")


def _path_rows(edges, path_index=None):
    rows = []
    for step, (_previous_state, move, next_state) in enumerate(edges, start=1):
        from_rc = square_from_mask(move["from_mask"])
        to_rc = square_from_mask(move["to_mask"])
        row = {
            "step": step,
            "from": from_rc,
            "to": to_rc,
            "dr": move["dr"],
            "dc": move["dc"],
            "side_after": next_state[3],
            "black_hex": hex(next_state[0]),
            "white_hex": hex(next_state[1]),
        }
        if path_index is not None:
            row = {"path": path_index, **row}
        rows.append(row)
    return rows


def _show_state_path(path, max_boards=16, size=1.6, tail=True):
    import math
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle

    if max_boards is not None and len(path) > max_boards:
        shown = path[-max_boards:] if tail else path[:max_boards]
        offset = len(path) - len(shown) if tail else 0
    else:
        shown = path
        offset = 0

    cols = min(4, max(1, len(shown)))
    rows = math.ceil(len(shown) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * size, rows * size))
    if not isinstance(axes, (list, tuple)):
        try:
            axes = axes.ravel().tolist()
        except AttributeError:
            axes = [axes]
    else:
        axes = list(axes)

    for ax in axes:
        ax.axis("off")

    for idx, (ax, state) in enumerate(zip(axes, shown), start=offset):
        _draw_state_on_axis(ax, state)
        ax.set_title(f"step {idx}, {state[3]}", fontsize=8)

    fig.suptitle(f"showing {len(shown)} of {len(path)} states")
    return fig, axes


def _show_many_state_paths(paths, max_boards_per_path=16, size=1.4, tail=True):
    import math
    import matplotlib.pyplot as plt

    if not paths:
        raise ValueError("no paths to display")

    shown_paths = []
    for path in paths:
        if max_boards_per_path is not None and len(path) > max_boards_per_path:
            shown = path[-max_boards_per_path:] if tail else path[:max_boards_per_path]
            offset = len(path) - len(shown) if tail else 0
        else:
            shown = path
            offset = 0
        shown_paths.append((shown, offset, len(path)))

    cols = max(len(shown) for shown, _offset, _length in shown_paths)
    rows = len(shown_paths)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * size, rows * size))
    try:
        flat_axes = axes.ravel().tolist()
    except AttributeError:
        flat_axes = [axes]

    for ax in flat_axes:
        ax.axis("off")

    for row_idx, (shown, offset, original_len) in enumerate(shown_paths):
        for col_idx, state in enumerate(shown):
            ax = flat_axes[row_idx * cols + col_idx]
            _draw_state_on_axis(ax, state)
            ax.set_title(f"path {row_idx}, step {offset + col_idx}", fontsize=7)
        if len(shown) < cols:
            ax = flat_axes[row_idx * cols + len(shown)]
            ax.text(
                0.5,
                0.5,
                f"{len(shown)} of {original_len}",
                ha="center",
                va="center",
                fontsize=8,
            )

    fig.suptitle(f"showing {len(paths)} path(s)")
    return fig, axes


def _draw_state_on_axis(ax, state):
    black, white, kings, _side = state
    from matplotlib.patches import Circle, Rectangle

    ax.set_xlim(-0.02, 8.02)
    ax.set_ylim(-0.02, 8.02)
    ax.set_aspect("equal")
    ax.axis("off")

    for r in range(8):
        for c in range(8):
            y = 7 - r
            bit = square_mask(r, c)
            fill = "#dddddd" if is_dark(r, c) else "white"
            ax.add_patch(Rectangle((c, y), 1, 1, fc=fill, ec="black", lw=0.5))
            if (black | white) & bit:
                is_black = bool(black & bit)
                piece_fill = "black" if is_black else "white"
                edge = "white" if is_black else "black"
                ax.add_patch(Circle((c + 0.5, y + 0.5), 0.36, fc=piece_fill, ec=edge, lw=0.8))
                if kings & bit:
                    ax.text(
                        c + 0.5,
                        y + 0.5,
                        "K",
                        ha="center",
                        va="center",
                        fontsize=7,
                        color=edge,
                        weight="bold",
                    )
    ax.add_patch(Rectangle((0, 0), 8, 8, fill=False, ec="black", lw=0.9, clip_on=False))


def _html_table(rows, title="state"):
    from IPython.display import HTML

    if not rows:
        return HTML(f"<p>No {title} states.</p>")

    headers = list(rows[0])
    header_html = "".join(f"<th>{header}</th>" for header in headers)
    body = []
    for row in rows:
        cells = []
        for header in headers:
            cells.append(f"<td>{row[header]}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")

    return HTML(
        "<table style='border-collapse: collapse; font-family: system-ui, sans-serif; "
        "font-size: 12px'>"
        f"<caption style='caption-side: top; text-align: left; font-weight: 600'>{title} states</caption>"
        f"<thead><tr>{header_html}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )

import heapq
import time
from pathlib import Path

from .bitboard import (
    initial_position,
    show_board,
    square_from_mask,
)

MASK32 = (1 << 32) - 1
BLACK_SHIFT = 0
WHITE_SHIFT = 32
KINGS_SHIFT = 64
SIDE_SHIFT = 96


def _build_row_tables():
    row64_to_nibble = [[0] * 256 for _ in range(2)]
    nibble_to_row64 = [[0] * 16 for _ in range(2)]

    for parity in (0, 1):
        cols = (1, 3, 5, 7) if parity == 0 else (0, 2, 4, 6)
        for row_byte in range(256):
            nibble = 0
            for offset, col in enumerate(cols):
                if row_byte & (1 << col):
                    nibble |= 1 << offset
            row64_to_nibble[parity][row_byte] = nibble

        for nibble in range(16):
            row_byte = 0
            for offset, col in enumerate(cols):
                if nibble & (1 << offset):
                    row_byte |= 1 << col
            nibble_to_row64[parity][nibble] = row_byte

    return row64_to_nibble, nibble_to_row64


ROW64_TO_NIBBLE, NIBBLE_TO_ROW64 = _build_row_tables()


def mask64_to32(mask):
    result = 0
    for row in range(8):
        row_byte = (mask >> (8 * row)) & 0xFF
        result |= ROW64_TO_NIBBLE[row & 1][row_byte] << (4 * row)
    return result


def mask32_to64(mask):
    mask &= MASK32
    result = 0
    for row in range(8):
        nibble = (mask >> (4 * row)) & 0xF
        result |= NIBBLE_TO_ROW64[row & 1][nibble] << (8 * row)
    return result


def square64_to32(mask):
    if not mask:
        return None
    row, col = square_from_mask(mask)
    if (row + col) % 2 != 1:
        raise ValueError("square is not playable")
    return row * 4 + (col // 2)


def square32_to64(square):
    if not (0 <= square < 32):
        raise ValueError(f"square out of range: {square!r}")
    row, offset = divmod(square, 4)
    col = 2 * offset + (1 if row % 2 == 0 else 0)
    return 1 << (8 * row + col)


def encode_state(state):
    black, white, kings, side = state
    side_bit = _side_to_bit(side)
    return (
        (mask64_to32(black) << BLACK_SHIFT)
        | (mask64_to32(white) << WHITE_SHIFT)
        | (mask64_to32(kings) << KINGS_SHIFT)
        | (side_bit << SIDE_SHIFT)
    )


def decode_state_key(state_key):
    black32, white32, kings32, side = split_state_key(state_key)
    return (
        mask32_to64(black32),
        mask32_to64(white32),
        mask32_to64(kings32),
        side,
    )


def split_state_key(state_key):
    black32 = (state_key >> BLACK_SHIFT) & MASK32
    white32 = (state_key >> WHITE_SHIFT) & MASK32
    kings32 = (state_key >> KINGS_SHIFT) & MASK32
    side = "W" if ((state_key >> SIDE_SHIFT) & 1) else "B"
    return black32, white32, kings32, side


def pack_state32(black32, white32, kings32=0, side="B"):
    return _encode_state32(black32, white32, _side_to_bit(side), kings32)


def state_key_record(state_key):
    return _state_key_record(state_key)


def _side_to_bit(side):
    if side == "B":
        return 0
    if side == "W":
        return 1
    raise ValueError(f"invalid side: {side!r}")


def _encode_state32(black32, white32, side_bit, kings32=0):
    return (
        (black32 & MASK32)
        | ((white32 & MASK32) << WHITE_SHIFT)
        | ((kings32 & MASK32) << KINGS_SHIFT)
        | (side_bit << SIDE_SHIFT)
    )


def _state_side_bit(state_key):
    return (state_key >> SIDE_SHIFT) & 1


def _build_square32_tables():
    square_to_row_col = []
    row_col_to_square = {}
    for row in range(8):
        for offset in range(4):
            col = 2 * offset + (1 if row % 2 == 0 else 0)
            square = row * 4 + offset
            square_to_row_col.append((row, col))
            row_col_to_square[(row, col)] = square
    return tuple(square_to_row_col), row_col_to_square


SQUARE32_TO_ROW_COL, ROW_COL_TO_SQUARE32 = _build_square32_tables()


(
    MOVE_FROM_BIT,
    MOVE_TO_BIT,
    MOVE_CAPTURED_BIT,
    MOVE_FROM_SQUARE,
    MOVE_TO_SQUARE,
    MOVE_CAPTURED_SQUARE,
    MOVE_DR,
    MOVE_DC,
    MOVE_PROMOTES,
) = range(9)


def _build_move32_tables():
    quiet = [[], []]
    captures = [[], []]
    for side_bit, step, promotion_row in ((0, 1, 7), (1, -1, 0)):
        for from_square, (row, col) in enumerate(SQUARE32_TO_ROW_COL):
            from_bit = 1 << from_square
            for dc in (-1, 1):
                to_row = row + step
                to_col = col + dc
                to_square = ROW_COL_TO_SQUARE32.get((to_row, to_col))
                if to_square is not None:
                    quiet[side_bit].append(
                        (
                            from_bit,
                            1 << to_square,
                            0,
                            from_square,
                            to_square,
                            None,
                            step,
                            dc,
                            to_row == promotion_row,
                        )
                    )

                to_row = row + 2 * step
                to_col = col + 2 * dc
                mid_row = row + step
                mid_col = col + dc
                to_square = ROW_COL_TO_SQUARE32.get((to_row, to_col))
                captured_square = ROW_COL_TO_SQUARE32.get((mid_row, mid_col))
                if to_square is not None and captured_square is not None:
                    captures[side_bit].append(
                        (
                            from_bit,
                            1 << to_square,
                            1 << captured_square,
                            from_square,
                            to_square,
                            captured_square,
                            2 * step,
                            2 * dc,
                            to_row == promotion_row,
                        )
                    )
    return tuple(tuple(moves) for moves in quiet), tuple(tuple(moves) for moves in captures)


QUIET_MOVES32, CAPTURE_MOVES32 = _build_move32_tables()


ROUND_METRIC_FIELDS = [
    "round",
    "elapsed_sec",
    "round_sec",
    "frontier_in",
    "processed",
    "skipped_expanded",
    "quiet_moves",
    "duplicate_states",
    "same_round_state_collisions",
    "prior_generation_state_hits",
    "existing_state_targets",
    "new_edges_to_existing_states",
    "new_transitions",
    "duplicate_transitions",
    "total_transitions",
    "new_states",
    "total_states",
    "next_frontier",
    "pruned_leaf_states",
    "pruned_leaf_states_total",
    "pruned_leaf_moves",
    "capture_moves",
    "promotion_moves",
    "capture_promotion_moves",
    "terminal_states_total",
    "expanded_total",
    "states_per_sec",
]


QUIET = "quiet"
FORCED_CAPTURE = "forced_capture"
PROMOTION = "promotion"
FORCED_CAPTURE_PROMOTION = "forced_capture+promotion"
TRANSITION_METADATA_KEYS = (
    QUIET,
    FORCED_CAPTURE,
    PROMOTION,
    FORCED_CAPTURE_PROMOTION,
)


class QuietPositionGraph:
    """Indexed DAG of quiet 12-vs-12 man-only checkers positions.

    States are distinct packed board/turn bit vectors. Quiet transitions are
    stored as round-layered hash maps from predecessor state key to successor
    state keys. Boundary exits use separate reason-keyed maps.
    """

    def __init__(self, start_state=None, pieces_per_side=12):
        self.pieces_per_side = pieces_per_side
        self.state_keys = []
        self.state_to_index = {}
        self.state_created_round = []
        self.frontier_keys = set()
        self.expanded_keys = set()
        self.terminal_keys = set()
        self.turn_metadata_maps = []
        self.quiet_successor_maps = []
        self.boundary_state_info = {}
        self.predecessor_keys = {}
        self.first_parent_key = {}
        self.transition_count_value = 0
        self.rounds = []
        self.csv_path = None
        self.jsonl_path = None
        self.stop_reason = None
        self._path_counts = None

        start_state = start_state or initial_position()
        start_key = start_state if isinstance(start_state, int) else encode_state(start_state)
        if not _is_quiet_state_key(start_key, pieces_per_side=self.pieces_per_side):
            raise ValueError(f"not a quiet {self.pieces_per_side}-man state: {start_state!r}")
        self._add_state_key(start_key, created_round=0)
        self.frontier_keys.add(start_key)

    @property
    def states(self):
        return [decode_state_key(state_key) for state_key in self.state_keys]

    @property
    def frontier(self):
        return {decode_state_key(state_key) for state_key in self.frontier_keys}

    @property
    def expanded(self):
        return {decode_state_key(state_key) for state_key in self.expanded_keys}

    @property
    def terminal_states(self):
        return {decode_state_key(state_key) for state_key in self.terminal_keys}

    @property
    def frontier_indices(self):
        return {self.state_to_index[state_key] for state_key in self.frontier_keys}

    @property
    def expanded_indices(self):
        return {self.state_to_index[state_key] for state_key in self.expanded_keys}

    @property
    def terminal_indices(self):
        return {self.state_to_index[state_key] for state_key in self.terminal_keys}

    @property
    def boundary_states(self):
        return {self.state_to_index[state_key]: dict(info) for state_key, info in self.boundary_state_info.items()}

    @property
    def transitions(self):
        rows = []
        for transition_index, round_number, predecessor_key, next_key in self._iter_quiet_edges():
            rows.append(
                {
                    "transition_index": transition_index,
                    "predecessor_index": self.state_to_index[predecessor_key],
                    "next_index": self.state_to_index[next_key],
                    "move": _quiet_transition_move_record(predecessor_key, next_key),
                    "created_next_state": (
                        self.first_parent_key.get(next_key) == predecessor_key
                        and self.state_created_round[self.state_to_index[next_key]] == round_number
                    ),
                    "round": round_number,
                }
            )
        return rows

    @property
    def transition_count(self):
        return self.transition_count_value

    @property
    def boundary_count(self):
        return len(self.boundary_state_info)

    @property
    def terminal_count(self):
        return len(self.terminal_keys)

    def __getitem__(self, key):
        return getattr(self, key)

    def _add_state_key(self, state_key, created_round):
        index = self.state_to_index.get(state_key)
        if index is not None:
            return index, False

        index = len(self.state_keys)
        self.state_to_index[state_key] = index
        self.state_keys.append(state_key)
        self.state_created_round.append(created_round)
        self._path_counts = None
        return index, True

    def _add_quiet_edge(self, round_successors, predecessor_key, next_key):
        targets = round_successors.setdefault(predecessor_key, set())
        if next_key in targets:
            return False

        targets.add(next_key)
        self.predecessor_keys.setdefault(next_key, set()).add(predecessor_key)
        self.first_parent_key.setdefault(next_key, predecessor_key)
        self.transition_count_value += 1
        self._path_counts = None
        return True

    def expand_frontier(self, max_processed=None):
        current_round = len(self.rounds) + 1
        round_metadata_maps = {metadata: {} for metadata in TRANSITION_METADATA_KEYS}
        round_successors = round_metadata_maps[QUIET]
        next_frontier = set()
        frontier = sorted(self.frontier_keys, key=_state_key_sort_key)
        frontier_in = len(frontier)
        processed = 0
        skipped_expanded = 0
        new_states = 0
        duplicate_states = 0
        same_round_state_collisions = 0
        prior_generation_state_hits = 0
        existing_state_targets = 0
        new_edges_to_existing_states = 0
        new_transitions = 0
        duplicate_transitions = 0
        quiet_moves = 0
        boundary_moves = 0
        boundary_source_states = 0
        terminal_source_states = 0
        capture_moves = 0
        promotion_moves = 0
        capture_promotion_moves = 0

        for state_key in frontier:
            if state_key in self.expanded_keys:
                skipped_expanded += 1
                continue
            if max_processed is not None and processed >= max_processed:
                next_frontier.add(state_key)
                continue

            if not _is_quiet_state_key(state_key, pieces_per_side=self.pieces_per_side):
                raise ValueError(f"not a quiet {self.pieces_per_side}-man state key: {state_key!r}")

            self.expanded_keys.add(state_key)
            processed += 1
            transition_info = _inspect_game_state_key(state_key)
            quiet_edges = transition_info["quiet_successors"]
            metadata_successors = transition_info["metadata_successors"]

            if quiet_edges is None:
                self.terminal_keys.add(state_key)
                terminal_source_states += 1
                continue

            state_had_boundary = False
            for metadata in (FORCED_CAPTURE, PROMOTION, FORCED_CAPTURE_PROMOTION):
                targets = metadata_successors[metadata]
                if not targets:
                    continue

                state_had_boundary = True
                boundary_moves += len(targets)
                if metadata == FORCED_CAPTURE:
                    capture_moves += len(targets)
                elif metadata == PROMOTION:
                    promotion_moves += len(targets)
                elif metadata == FORCED_CAPTURE_PROMOTION:
                    capture_promotion_moves += len(targets)

                self._record_boundary_key(state_key, metadata, len(targets))
                round_metadata_maps[metadata].setdefault(state_key, set()).update(targets)

            for next_key in quiet_edges:
                quiet_moves += 1
                next_index, created = self._add_state_key(next_key, created_round=current_round)
                if created:
                    next_frontier.add(next_key)
                    new_states += 1
                else:
                    duplicate_states += 1
                    existing_state_targets += 1
                    if self.state_created_round[next_index] == current_round:
                        same_round_state_collisions += 1
                    else:
                        prior_generation_state_hits += 1

                added = self._add_quiet_edge(round_successors, state_key, next_key)
                if added:
                    new_transitions += 1
                    if not created:
                        new_edges_to_existing_states += 1
                else:
                    duplicate_transitions += 1

            if state_had_boundary:
                boundary_source_states += 1

        self.turn_metadata_maps.append(round_metadata_maps)
        self.quiet_successor_maps.append(round_successors)
        self.frontier_keys = next_frontier

        return {
            "frontier_in": frontier_in,
            "processed": processed,
            "skipped_expanded": skipped_expanded,
            "new_states": new_states,
            "duplicate_states": duplicate_states,
            "same_round_state_collisions": same_round_state_collisions,
            "prior_generation_state_hits": prior_generation_state_hits,
            "existing_state_targets": existing_state_targets,
            "new_edges_to_existing_states": new_edges_to_existing_states,
            "new_transitions": new_transitions,
            "duplicate_transitions": duplicate_transitions,
            "total_transitions": self.transition_count_value,
            "total_states": len(self.state_keys),
            "quiet_moves": quiet_moves,
            "boundary_moves": boundary_moves,
            "boundary_source_states": boundary_source_states,
            "terminal_source_states": terminal_source_states,
            "capture_moves": capture_moves,
            "promotion_moves": promotion_moves,
            "capture_promotion_moves": capture_promotion_moves,
            "boundary_states": len(self.boundary_state_info),
            "terminal_states": len(self.terminal_keys),
            "next_frontier": len(self.frontier_keys),
            "expanded_total": len(self.expanded_keys),
        }

    def run_round(self, started=None, max_processed=None):
        started = started or time.perf_counter()
        round_started = time.perf_counter()
        result = self.expand_frontier(max_processed=max_processed)
        round_sec = time.perf_counter() - round_started
        elapsed_sec = time.perf_counter() - started
        states_per_sec = result["processed"] / round_sec if round_sec and result["processed"] else 0.0

        row = {
            "round": len(self.rounds) + 1,
            "elapsed_sec": round(elapsed_sec, 6),
            "round_sec": round(round_sec, 6),
            "frontier_in": result["frontier_in"],
            "processed": result["processed"],
            "skipped_expanded": result["skipped_expanded"],
            "quiet_moves": result["quiet_moves"],
            "duplicate_states": result["duplicate_states"],
            "same_round_state_collisions": result["same_round_state_collisions"],
            "prior_generation_state_hits": result["prior_generation_state_hits"],
            "existing_state_targets": result["existing_state_targets"],
            "new_edges_to_existing_states": result["new_edges_to_existing_states"],
            "new_transitions": result["new_transitions"],
            "duplicate_transitions": result["duplicate_transitions"],
            "total_transitions": result["total_transitions"],
            "new_states": result["new_states"],
            "total_states": result["total_states"],
            "next_frontier": result["next_frontier"],
            "pruned_leaf_states": result["boundary_source_states"],
            "pruned_leaf_states_total": result["boundary_states"],
            "pruned_leaf_moves": result["boundary_moves"],
            "capture_moves": result["capture_moves"],
            "promotion_moves": result["promotion_moves"],
            "capture_promotion_moves": result["capture_promotion_moves"],
            "terminal_states_total": result["terminal_states"],
            "expanded_total": result["expanded_total"],
            "states_per_sec": round(states_per_sec, 2),
        }
        self.rounds.append(row)
        return row

    def run(
        self,
        max_rounds=None,
        max_seconds=None,
        max_total_states=None,
        max_processed_per_round=None,
        on_round=None,
    ):
        started = time.perf_counter()
        self.stop_reason = "frontier exhausted"
        while self.frontier_keys:
            elapsed = time.perf_counter() - started
            if max_rounds is not None and len(self.rounds) >= max_rounds:
                self.stop_reason = "max rounds reached"
                break
            if max_seconds is not None and elapsed >= max_seconds:
                self.stop_reason = "max seconds reached"
                break
            if max_total_states is not None and len(self.state_keys) >= max_total_states:
                self.stop_reason = "max total states reached"
                break

            row = self.run_round(started=started, max_processed=max_processed_per_round)
            if on_round is not None:
                on_round(self, row)
        return self

    def _record_boundary_key(self, state_key, reason, count=1):
        info = self.boundary_state_info.setdefault(
            state_key,
            {
                FORCED_CAPTURE: 0,
                PROMOTION: 0,
                FORCED_CAPTURE_PROMOTION: 0,
                "moves": 0,
            },
        )
        info[reason] += count
        info["moves"] += count

    def summary(self):
        latest = self.rounds[-1] if self.rounds else {}
        return {
            "stop_reason": self.stop_reason,
            "rounds": len(self.rounds),
            "total_states": len(self.state_keys),
            "frontier": len(self.frontier_keys),
            "expanded": len(self.expanded_keys),
            "transitions": self.transition_count_value,
            "pruned_boundary_states": len(self.boundary_state_info),
            "terminal_states": len(self.terminal_keys),
            "latest_round": latest,
            "csv_path": str(self.csv_path) if self.csv_path else None,
            "jsonl_path": str(self.jsonl_path) if self.jsonl_path else None,
        }

    def state_index(self, state):
        if isinstance(state, int) and 0 <= state < len(self.state_keys):
            return state
        state_key = state if isinstance(state, int) else encode_state(state)
        try:
            return self.state_to_index[state_key]
        except KeyError as exc:
            raise KeyError("state is not in this graph") from exc

    def state(self, state_index):
        return decode_state_key(self.state_keys[state_index])

    def _resolve_state_key(self, state_or_index):
        if isinstance(state_or_index, int) and 0 <= state_or_index < len(self.state_keys):
            return self.state_keys[state_or_index]
        return normalize_state_key(state_or_index)

    def inspect_state(self, state_or_index):
        state_key = self._resolve_state_key(state_or_index)
        info = inspect_game_state(state_key, pieces_per_side=self.pieces_per_side)
        info["state_index"] = self.state_to_index.get(state_key)
        return info

    def transition_map(self, round_number, metadata=QUIET):
        if metadata not in TRANSITION_METADATA_KEYS:
            raise ValueError(f"unknown transition metadata: {metadata!r}")
        return self.turn_metadata_maps[round_number - 1][metadata]

    def metadata_maps_df(self):
        rows = []
        for round_number, round_maps in enumerate(self.turn_metadata_maps, start=1):
            for metadata in TRANSITION_METADATA_KEYS:
                source_map = round_maps[metadata]
                target_count = sum(len(targets) for targets in source_map.values())
                distinct_targets = set()
                for targets in source_map.values():
                    distinct_targets.update(targets)
                rows.append(
                    {
                        "round": round_number,
                        "metadata": metadata,
                        "source_states": len(source_map),
                        "edges": target_count,
                        "distinct_target_states": len(distinct_targets),
                    }
                )
        return _dataframe(rows)

    def tablebase_summary_df(self):
        row = self.summary()
        metadata_df = self.metadata_maps_df()
        if not metadata_df.empty:
            for metadata in TRANSITION_METADATA_KEYS:
                subset = metadata_df[metadata_df["metadata"] == metadata]
                label = _metadata_column_label(metadata)
                row[f"{label}_edges"] = int(subset["edges"].sum())
                row[f"{label}_source_states"] = int(subset["source_states"].sum())
        return _dataframe([row])

    def terminal_list(self):
        return [decode_state_key(state_key) for state_key in sorted(self.terminal_keys, key=_state_key_sort_key)]

    def boundary_list(self):
        return [decode_state_key(state_key) for state_key in sorted(self.boundary_state_info, key=_state_key_sort_key)]

    def terminal_state(self, index=0):
        terminal_key = sorted(self.terminal_keys, key=_state_key_sort_key)[index]
        return decode_state_key(terminal_key)

    def boundary_state(self, index=0):
        boundary_key = sorted(self.boundary_state_info, key=_state_key_sort_key)[index]
        return decode_state_key(boundary_key)

    def rounds_df(self):
        return _dataframe(self.rounds)

    def states_df(
        self,
        which="all",
        sort=False,
        include_flags=True,
        include_path_counts=False,
        include_tuple=False,
    ):
        indices = self._select_state_indices(which)
        if sort:
            indices = sorted(indices, key=lambda index: _state_key_sort_key(self.state_keys[index]))
        path_counts = self.path_counts() if include_path_counts else None

        rows = []
        for state_index in indices:
            state_key = self.state_keys[state_index]
            first_parent_key = self.first_parent_key.get(state_key)
            row = {
                "state_index": state_index,
                "state_key": state_key,
                "quiet_depth": _quiet_state_depth_from_key(state_key),
                "predecessors": len(self.predecessor_keys.get(state_key, ())),
                "first_parent_state_index": (
                    None if first_parent_key is None else self.state_to_index[first_parent_key]
                ),
                "first_parent_state_key": first_parent_key,
            }
            row.update(_state_key_record(state_key, include_tuple=include_tuple))
            if include_flags:
                row.update(
                    {
                        "in_frontier": state_key in self.frontier_keys,
                        "expanded": state_key in self.expanded_keys,
                        "is_terminal": state_key in self.terminal_keys,
                        "is_boundary": state_key in self.boundary_state_info,
                    }
                )
            if path_counts is not None:
                row["path_count"] = path_counts[state_index]
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
        indices = self._select_state_indices("boundary")
        if sort:
            indices = sorted(indices, key=lambda index: _state_key_sort_key(self.state_keys[index]))
        path_counts = self.path_counts() if include_path_counts else None

        rows = []
        for state_index in indices:
            state_key = self.state_keys[state_index]
            info = self.boundary_state_info[state_key]
            row = {
                "state_index": state_index,
                "state_key": state_key,
                "quiet_depth": _quiet_state_depth_from_key(state_key),
                "predecessors": len(self.predecessor_keys.get(state_key, ())),
                "forced_capture": info.get(FORCED_CAPTURE, 0),
                "promotion": info.get(PROMOTION, 0),
                "forced_capture_promotion": info.get(FORCED_CAPTURE_PROMOTION, 0),
                "boundary_moves": info.get("moves", 0),
            }
            row.update(_state_key_record(state_key, include_tuple=include_tuple))
            if path_counts is not None:
                row["path_count"] = path_counts[state_index]
            rows.append(row)
        return _dataframe(rows)

    def transitions_df(
        self,
        predecessor_index=None,
        next_index=None,
        transition_indices=None,
        include_state_fields=False,
        include_tuple=False,
    ):
        transition_filter = set(transition_indices) if transition_indices is not None else None
        predecessor_key = None if predecessor_index is None else self.state_keys[predecessor_index]
        next_key_filter = None if next_index is None else self.state_keys[next_index]
        rows = []
        for transition_index, round_number, from_key, to_key in self._iter_quiet_edges():
            if transition_filter is not None and transition_index not in transition_filter:
                continue
            if predecessor_key is not None and from_key != predecessor_key:
                continue
            if next_key_filter is not None and to_key != next_key_filter:
                continue

            from_index = self.state_to_index[from_key]
            to_index = self.state_to_index[to_key]
            row = {
                "transition_index": transition_index,
                "predecessor_index": from_index,
                "next_index": to_index,
                "round": round_number,
                "created_next_state": (
                    self.first_parent_key.get(to_key) == from_key and self.state_created_round[to_index] == round_number
                ),
                "predecessor_depth": _quiet_state_depth_from_key(from_key),
                "next_depth": _quiet_state_depth_from_key(to_key),
            }
            row.update(_quiet_transition_move_record(from_key, to_key))
            if include_state_fields:
                row.update(
                    _state_key_record(
                        from_key,
                        prefix="predecessor_",
                        include_tuple=include_tuple,
                    )
                )
                row.update(
                    _state_key_record(
                        to_key,
                        prefix="next_",
                        include_tuple=include_tuple,
                    )
                )
            rows.append(row)
        return _dataframe(rows)

    def boundary_edges_df(
        self,
        state_index=None,
        include_state_fields=False,
        include_tuple=False,
    ):
        rows = []
        state_key_filter = None if state_index is None else self.state_keys[state_index]
        edge_index = 0
        for round_number, metadata, state_key, next_key in self._iter_boundary_edges():
            if state_key_filter is not None and state_key != state_key_filter:
                continue

            row = {
                "boundary_edge_index": edge_index,
                "state_index": self.state_to_index[state_key],
                "next_index": self.state_to_index.get(next_key),
                "round": round_number,
                "metadata": metadata,
                "forced_capture": metadata in (FORCED_CAPTURE, FORCED_CAPTURE_PROMOTION),
                "promotion": metadata in (PROMOTION, FORCED_CAPTURE_PROMOTION),
                "state_key": state_key,
                "next_state_key": next_key,
                "quiet_depth": _quiet_state_depth_from_key(state_key),
            }
            row.update(_quiet_transition_move_record(state_key, next_key))
            if include_state_fields:
                row.update(
                    _state_key_record(
                        state_key,
                        prefix="predecessor_",
                        include_tuple=include_tuple,
                    )
                )
                row.update(
                    _state_key_record(
                        next_key,
                        prefix="next_",
                        include_tuple=include_tuple,
                    )
                )
            rows.append(row)
            edge_index += 1
        return _dataframe(rows)

    def predecessors_df(self, state_index, include_state_fields=False):
        return self.transitions_df(
            next_index=state_index,
            include_state_fields=include_state_fields,
        )

    def successors_df(self, predecessor_index, include_state_fields=False):
        return self.transitions_df(
            predecessor_index=predecessor_index,
            include_state_fields=include_state_fields,
        )

    def path_counts(self, refresh=False):
        if self._path_counts is not None and not refresh:
            return self._path_counts

        counts = [0] * len(self.state_keys)
        for state_index in sorted(
            range(len(self.state_keys)),
            key=lambda index: _quiet_state_depth_from_key(self.state_keys[index]),
        ):
            state_key = self.state_keys[state_index]
            predecessors = self.predecessor_keys.get(state_key)
            if not predecessors:
                counts[state_index] = 1
            else:
                counts[state_index] = sum(
                    counts[self.state_to_index[predecessor_key]] for predecessor_key in predecessors
                )
        self._path_counts = counts
        return counts

    def path_count_distribution_df(self, which="all", max_path_count=10, refresh=False):
        counts = self.path_counts(refresh=refresh)
        distribution = {}
        overflow = 0
        for state_index in self._select_state_indices(which):
            path_count = counts[state_index]
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
        self,
        which="all",
        limit=50,
        max_path_count=None,
        include_flags=True,
        include_tuple=False,
        refresh=False,
    ):
        counts = self.path_counts(refresh=refresh)

        def eligible_indices():
            for state_index in self._select_state_indices(which):
                path_count = counts[state_index]
                if max_path_count is None or path_count <= max_path_count:
                    yield state_index

        def sort_key(state_index):
            return (
                counts[state_index],
                _quiet_state_depth_from_key(self.state_keys[state_index]),
                _state_key_sort_key(self.state_keys[state_index]),
            )

        if limit is None:
            selected = sorted(eligible_indices(), key=sort_key)
        else:
            selected = heapq.nsmallest(limit, eligible_indices(), key=sort_key)

        rows = []
        for state_index in selected:
            state_key = self.state_keys[state_index]
            row = {
                "state_index": state_index,
                "state_key": state_key,
                "path_count": counts[state_index],
                "quiet_depth": _quiet_state_depth_from_key(state_key),
                "first_path_len": len(self.path_to_state_index(state_index)) - 1,
                "predecessors": len(self.predecessor_keys.get(state_key, ())),
            }
            row.update(_state_key_record(state_key, include_tuple=include_tuple))
            if include_flags:
                row.update(
                    {
                        "in_frontier": state_key in self.frontier_keys,
                        "expanded": state_key in self.expanded_keys,
                        "is_terminal": state_key in self.terminal_keys,
                        "is_boundary": state_key in self.boundary_state_info,
                    }
                )
            if state_key in self.boundary_state_info:
                info = self.boundary_state_info[state_key]
                row.update(
                    {
                        "forced_capture": info.get(FORCED_CAPTURE, 0),
                        "promotion": info.get(PROMOTION, 0),
                        "forced_capture_promotion": info.get(FORCED_CAPTURE_PROMOTION, 0),
                        "boundary_moves": info.get("moves", 0),
                    }
                )
            rows.append(row)
        return _dataframe(rows)

    def unique_path_states_df(
        self,
        which="all",
        limit=50,
        include_flags=True,
        include_tuple=False,
        refresh=False,
    ):
        return self.least_path_count_states_df(
            which=which,
            limit=limit,
            max_path_count=1,
            include_flags=include_flags,
            include_tuple=include_tuple,
            refresh=refresh,
        )

    def path_to_state_index(self, state_index):
        path = []
        seen = set()
        current_key = self.state_keys[state_index]
        while True:
            if current_key in seen:
                raise ValueError("cycle found in first-parent map")
            seen.add(current_key)
            path.append(self.state_to_index[current_key])
            parent_key = self.first_parent_key.get(current_key)
            if parent_key is None:
                break
            current_key = parent_key
        path.reverse()
        return path

    def path_to_state(self, state):
        return [decode_state_key(self.state_keys[index]) for index in self.path_to_state_index(self.state_index(state))]

    def path_to_terminal(self, index=0):
        terminal_key = sorted(self.terminal_keys, key=_state_key_sort_key)[index]
        terminal_index = self.state_to_index[terminal_key]
        return [
            decode_state_key(self.state_keys[state_index]) for state_index in self.path_to_state_index(terminal_index)
        ]

    def show_state(self, state_or_index, dots=0, size=1.5):
        if isinstance(state_or_index, int) and 0 <= state_or_index < len(self.state_keys):
            state = decode_state_key(self.state_keys[state_or_index])
        elif isinstance(state_or_index, int):
            state = decode_state_key(state_or_index)
        else:
            state = state_or_index
        black, white, kings, side = state
        fig, axes = show_board(black, white, kings, dots=dots, size=size)
        fig.suptitle(f"side to move: {side}")
        return fig, axes

    def show_terminal(self, index=0, size=1.5):
        terminal_key = sorted(self.terminal_keys, key=_state_key_sort_key)[index]
        terminal_index = self.state_to_index[terminal_key]
        return self.show_state(terminal_index, size=size)

    def _select_state_indices(self, which):
        if isinstance(which, str):
            if which == "all":
                return list(range(len(self.state_keys)))
            if which == "frontier":
                return [self.state_to_index[state_key] for state_key in self.frontier_keys]
            if which == "expanded":
                return [self.state_to_index[state_key] for state_key in self.expanded_keys]
            if which == "terminal":
                return [
                    self.state_to_index[state_key] for state_key in sorted(self.terminal_keys, key=_state_key_sort_key)
                ]
            if which == "boundary":
                return [
                    self.state_to_index[state_key]
                    for state_key in sorted(self.boundary_state_info, key=_state_key_sort_key)
                ]
            raise ValueError("which must be 'all', 'frontier', 'expanded', 'terminal', or 'boundary'")
        return list(which)

    def _iter_quiet_edges(self):
        transition_index = 0
        for round_number, successor_map in enumerate(self.quiet_successor_maps, start=1):
            for predecessor_key in sorted(successor_map, key=_state_key_sort_key):
                for next_key in sorted(successor_map[predecessor_key], key=_state_key_sort_key):
                    yield transition_index, round_number, predecessor_key, next_key
                    transition_index += 1

    def _iter_boundary_edges(self):
        for round_number, round_maps in enumerate(self.turn_metadata_maps, start=1):
            for metadata in (FORCED_CAPTURE, PROMOTION, FORCED_CAPTURE_PROMOTION):
                source_map = round_maps.get(metadata, {})
                for state_key in sorted(source_map, key=_state_key_sort_key):
                    for next_key in sorted(source_map[state_key], key=_state_key_sort_key):
                        yield round_number, metadata, state_key, next_key


def run_quiet_graph(
    start_state=None,
    pieces_per_side=12,
    max_rounds=None,
    max_seconds=None,
    max_total_states=None,
    max_processed_per_round=None,
    on_round=None,
):
    graph = QuietPositionGraph(start_state=start_state, pieces_per_side=pieces_per_side)
    return graph.run(
        max_rounds=max_rounds,
        max_seconds=max_seconds,
        max_total_states=max_total_states,
        max_processed_per_round=max_processed_per_round,
        on_round=on_round,
    )


def load_round_metrics(path):
    import pandas as pd

    return pd.read_csv(Path(path))


def _dataframe(rows):
    import pandas as pd

    return pd.DataFrame.from_records(rows)


def _metadata_column_label(metadata):
    return metadata.replace("+", "_")


def normalize_state_key(state):
    return state if isinstance(state, int) else encode_state(state)


def inspect_game_state(state, pieces_per_side=12):
    """Return legal quiet successors and boundary transition metadata.

    ``quiet_successors`` is a set of non-capturing, non-promoting successor
    state keys. It is ``None`` only when the state has no legal moves. Boundary
    successors are grouped by low-cardinality metadata buckets:

    - ``forced_capture``: legal capture successors, where forced capture is a
      property of the source state.
    - ``promotion``: non-capture successors whose target contains a new king.
    - ``forced_capture+promotion``: capture successors whose target promotes.
    """
    state_key = normalize_state_key(state)
    if not _is_supported_man_source_key(state_key, pieces_per_side=pieces_per_side):
        raise ValueError("state must be a man-only packed state with the configured piece counts")
    return _inspect_game_state_key(state_key)


def _is_quiet_state_key(state_key, pieces_per_side=12):
    black32, white32, kings32, side = split_state_key(state_key)
    return (
        side in ("B", "W")
        and kings32 == 0
        and not (black32 & white32)
        and black32.bit_count() == pieces_per_side
        and white32.bit_count() == pieces_per_side
    )


def _is_supported_man_source_key(state_key, pieces_per_side=12):
    return _is_quiet_state_key(state_key, pieces_per_side=pieces_per_side)


def _inspect_game_state_key(state_key):
    black32 = state_key & MASK32
    white32 = (state_key >> WHITE_SHIFT) & MASK32
    kings32 = (state_key >> KINGS_SHIFT) & MASK32
    if kings32:
        raise NotImplementedError("the current transition generator supports man-only sources")

    side_bit = _state_side_bit(state_key)
    mine = black32 if side_bit == 0 else white32
    theirs = white32 if side_bit == 0 else black32
    occupied = black32 | white32

    metadata_successors = {metadata: set() for metadata in TRANSITION_METADATA_KEYS}
    for move in CAPTURE_MOVES32[side_bit]:
        if not (mine & move[MOVE_FROM_BIT]):
            continue
        if occupied & move[MOVE_TO_BIT]:
            continue
        if not (theirs & move[MOVE_CAPTURED_BIT]):
            continue
        next_key = _apply_move32_to_key(state_key, move)
        metadata = FORCED_CAPTURE_PROMOTION if move[MOVE_PROMOTES] else FORCED_CAPTURE
        metadata_successors[metadata].add(next_key)

    forced_capture = bool(metadata_successors[FORCED_CAPTURE] or metadata_successors[FORCED_CAPTURE_PROMOTION])
    if forced_capture:
        return {
            "state_key": state_key,
            "quiet_successors": set(),
            "forced_capture": True,
            "promotion_possible": bool(metadata_successors[FORCED_CAPTURE_PROMOTION]),
            "terminal": False,
            "metadata_successors": metadata_successors,
        }

    quiet_edges = []
    for move in QUIET_MOVES32[side_bit]:
        if not (mine & move[MOVE_FROM_BIT]):
            continue
        if occupied & move[MOVE_TO_BIT]:
            continue

        next_key = _apply_move32_to_key(state_key, move)
        if move[MOVE_PROMOTES]:
            metadata_successors[PROMOTION].add(next_key)
        else:
            quiet_edges.append(next_key)
            metadata_successors[QUIET].add(next_key)

    has_legal_move = bool(quiet_edges or metadata_successors[PROMOTION])
    return {
        "state_key": state_key,
        "quiet_successors": set(quiet_edges) if has_legal_move else None,
        "forced_capture": False,
        "promotion_possible": bool(metadata_successors[PROMOTION]),
        "terminal": not has_legal_move,
        "metadata_successors": metadata_successors,
    }


def _apply_move32_to_key(state_key, move):
    black32 = state_key & MASK32
    white32 = (state_key >> WHITE_SHIFT) & MASK32
    kings32 = (state_key >> KINGS_SHIFT) & MASK32
    side_bit = _state_side_bit(state_key)

    from_bit = move[MOVE_FROM_BIT]
    to_bit = move[MOVE_TO_BIT]
    captured_bit = move[MOVE_CAPTURED_BIT]

    if side_bit == 0:
        next_black32 = (black32 & ~from_bit) | to_bit
        next_white32 = white32 & ~captured_bit
    else:
        next_black32 = black32 & ~captured_bit
        next_white32 = (white32 & ~from_bit) | to_bit

    mover_was_king = bool(kings32 & from_bit)
    next_kings32 = kings32 & ~from_bit & ~captured_bit
    if mover_was_king or move[MOVE_PROMOTES]:
        next_kings32 |= to_bit

    return _encode_state32(next_black32, next_white32, 1 - side_bit, next_kings32)


def _quiet_transition_move_record(predecessor_key, next_key):
    side_bit = _state_side_bit(predecessor_key)
    predecessor_black32 = predecessor_key & MASK32
    predecessor_white32 = (predecessor_key >> WHITE_SHIFT) & MASK32
    predecessor_kings32 = (predecessor_key >> KINGS_SHIFT) & MASK32
    next_black32 = next_key & MASK32
    next_white32 = (next_key >> WHITE_SHIFT) & MASK32
    next_kings32 = (next_key >> KINGS_SHIFT) & MASK32

    if side_bit == 0:
        from_bits = predecessor_black32 & ~next_black32
        to_bits = next_black32 & ~predecessor_black32
        captured_bits = predecessor_white32 & ~next_white32
    else:
        from_bits = predecessor_white32 & ~next_white32
        to_bits = next_white32 & ~predecessor_white32
        captured_bits = predecessor_black32 & ~next_black32

    from_square = from_bits.bit_length() - 1
    to_square = to_bits.bit_length() - 1
    captured_square = None if not captured_bits else captured_bits.bit_length() - 1
    from_r, from_c = SQUARE32_TO_ROW_COL[from_square]
    to_r, to_c = SQUARE32_TO_ROW_COL[to_square]
    if captured_square is None:
        captured_r = captured_c = None
    else:
        captured_r, captured_c = SQUARE32_TO_ROW_COL[captured_square]
    promoted = bool((next_kings32 & to_bits) and not (predecessor_kings32 & from_bits))
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
        "dr": to_r - from_r,
        "dc": to_c - from_c,
        "is_capture": bool(captured_bits),
        "is_promotion": promoted,
    }


def _state_key_record(state_key, prefix="", include_tuple=False):
    black32, white32, kings32, side = split_state_key(state_key)
    row = {
        f"{prefix}state_key": state_key,
        f"{prefix}black32": black32,
        f"{prefix}white32": white32,
        f"{prefix}kings32": kings32,
        f"{prefix}side": side,
    }
    if include_tuple:
        row[f"{prefix}state"] = decode_state_key(state_key)
    return row


def _state_key_sort_key(state_key):
    black32, white32, kings32, side = split_state_key(state_key)
    return (side, black32, white32, kings32)


def _quiet_state_score_from_key(state_key):
    black32, white32, _kings32, _side = split_state_key(state_key)
    return _mask32_row_sum(black32) - _mask32_row_sum(white32)


def _quiet_state_depth_from_key(state_key):
    return _quiet_state_score_from_key(state_key) - _initial_quiet_state_score()


def _initial_quiet_state_score():
    score = getattr(_initial_quiet_state_score, "_score", None)
    if score is None:
        score = _quiet_state_score_from_key(encode_state(initial_position()))
        _initial_quiet_state_score._score = score
    return score


def _mask32_row_sum(mask):
    total = 0
    for row in range(8):
        total += row * ((mask >> (4 * row)) & 0xF).bit_count()
    return total

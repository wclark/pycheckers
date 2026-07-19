"""Native 32-bit playable-square encodings for checkers boards."""

MASK32 = (1 << 32) - 1


def is_playable_square(row, col):
    """Return whether ``(row, col)`` is one of the 32 playable board squares."""

    return 0 <= int(row) < 8 and 0 <= int(col) < 8 and (int(row) + int(col)) % 2 == 1


def square_index32(row, col):
    """Return the 0-based playable-square index for ``(row, col)``."""

    row = int(row)
    col = int(col)
    if not is_playable_square(row, col):
        raise ValueError(f"square is not playable: {(row, col)}")
    return row * 4 + (col // 2)


def square_mask32(row, col):
    """Return a one-bit 32-bit mask for a playable board square."""

    return 1 << square_index32(row, col)


def square_coords32(square):
    """Return ``(row, col)`` for a playable-square index."""

    square = int(square)
    if not (0 <= square < 32):
        raise ValueError(f"square out of range: {square!r}")
    row, offset = divmod(square, 4)
    col = 2 * offset + (1 if row % 2 == 0 else 0)
    return row, col


def square_from_mask32(mask):
    """Return ``(row, col)`` for a one-bit 32-bit playable-square mask."""

    mask = int(mask)
    if mask <= 0 or mask & (mask - 1):
        raise ValueError("mask must contain exactly one bit")
    square = mask.bit_length() - 1
    if square >= 32:
        raise ValueError("mask is outside the playable-square board")
    return square_coords32(square)


def playable_squares():
    """Return all playable squares as ``(row, col, mask)`` tuples."""

    return tuple(
        (row, col, square_mask32(row, col)) for row in range(8) for col in range(8) if is_playable_square(row, col)
    )

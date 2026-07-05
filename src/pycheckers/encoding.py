"""32-bit playable-square encodings for checkers boards."""

from .bitboard import square_from_mask

MASK32 = (1 << 32) - 1


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
    """Pack an 8x8 board mask into the 32 playable squares."""

    result = 0
    for row in range(8):
        row_byte = (int(mask) >> (8 * row)) & 0xFF
        result |= ROW64_TO_NIBBLE[row & 1][row_byte] << (4 * row)
    return result & MASK32


def mask32_to64(mask):
    """Expand a playable-square mask back to the 8x8 board layout."""

    mask = int(mask) & MASK32
    result = 0
    for row in range(8):
        nibble = (mask >> (4 * row)) & 0xF
        result |= NIBBLE_TO_ROW64[row & 1][nibble] << (8 * row)
    return result


def square64_to32(mask):
    """Return the playable-square index for a one-bit 8x8 board mask."""

    if not mask:
        return None
    row, col = square_from_mask(int(mask))
    if (row + col) % 2 != 1:
        raise ValueError("square is not playable")
    return row * 4 + (col // 2)


def square32_to64(square):
    """Return an 8x8 one-bit mask for a playable-square index."""

    if not (0 <= int(square) < 32):
        raise ValueError(f"square out of range: {square!r}")
    row, offset = divmod(int(square), 4)
    col = 2 * offset + (1 if row % 2 == 0 else 0)
    return 1 << (8 * row + col)


def square_mask32_from64(mask):
    """Convert a one-bit 8x8 board mask into a one-bit playable-square mask."""

    square = square64_to32(mask)
    if square is None:
        return 0
    return 1 << square

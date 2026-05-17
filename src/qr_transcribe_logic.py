"""Pure logic for the QR transcribe screen.

Kept LVGL-free and outside `gui.screens` so unit tests can import it
without pulling in the framebuffer-dependent screen package.
"""


def adaptive_grid_size(s):
    """Pick an N x N grid so each zone holds ~12-18 modules per side.

    Argument s is the bitmap side length returned by qrcode.encode()
    (the QR plus quiet-zone border, padded to byte stride).
    """
    if s <= 28:
        return 2
    if s <= 44:
        return 3
    if s <= 60:
        return 4
    return 5


def zone_bounds(s, n, zone_r, zone_c):
    """Return (r0, c0, r1, c1) bitmap-row/col slice for the given zone.

    The last row and last column absorb any remainder so the whole
    bitmap is covered. Coordinates are 0-indexed; r1/c1 are exclusive.
    """
    step = s // n
    r0 = zone_r * step
    c0 = zone_c * step
    r1 = s if zone_r == n - 1 else r0 + step
    c1 = s if zone_c == n - 1 else c0 + step
    return (r0, c0, r1, c1)


def module_at(raw, s, r, c):
    """Return 0 or 1 for the bit at (row, col) of an SxS 1-bit bitmap.

    `raw` is a bytes/bytearray packed MSB-first, row-major, as produced
    by the qrcode usermod's qrcode.encode().
    """
    idx = r * s + c
    byte = raw[idx >> 3]
    return (byte >> (7 - (idx & 7))) & 1


def next_zone(n, zone_r, zone_c, direction):
    """Move one step in the given direction, clamped at the N x N edges."""
    if direction == "up":
        return (max(0, zone_r - 1), zone_c)
    if direction == "down":
        return (min(n - 1, zone_r + 1), zone_c)
    if direction == "left":
        return (zone_r, max(0, zone_c - 1))
    if direction == "right":
        return (zone_r, min(n - 1, zone_c + 1))
    return (zone_r, zone_c)


def iter_zone_modules(raw, s, n, zone_r, zone_c):
    """Yield (zone_row, zone_col, is_dark) for each module in the zone.

    zone_row and zone_col are 0-indexed within the zone (zone-local).
    is_dark is 1 if the QR has a dark module at the absolute position
    (r0 + zone_row, c0 + zone_col), else 0.
    """
    r0, c0, r1, c1 = zone_bounds(s, n, zone_r, zone_c)
    for zr in range(r1 - r0):
        for zc in range(c1 - c0):
            yield zr, zc, module_at(raw, s, r0 + zr, c0 + zc)


def clamp_zone(n, zone_r, zone_c):
    """Clamp a zone index to [0, n-1] in each axis.

    Used when the user reduces N from the transcribe screen and the
    current (zone_r, zone_c) would now be off the grid.
    """
    return min(zone_r, n - 1), min(zone_c, n - 1)

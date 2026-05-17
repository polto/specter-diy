from unittest import TestCase
from qr_transcribe_logic import (
    adaptive_grid_size, zone_bounds, module_at, next_zone,
    iter_zone_modules, clamp_zone,
)


class QRTranscribeLogicTest(TestCase):
    def test_adaptive_grid_size(self):
        """Grid size N is chosen so each zone holds ~12-18 modules per side."""
        # S values correspond to the byte-stride sizes returned by qrcode.encode()
        # for QR versions 1, 2, 5, 8, 13 respectively.
        self.assertEqual(adaptive_grid_size(28), 2)   # v1 (21 modules)
        self.assertEqual(adaptive_grid_size(36), 3)   # v2 (25 modules)
        self.assertEqual(adaptive_grid_size(44), 3)   # v4 (33 modules)
        self.assertEqual(adaptive_grid_size(52), 4)   # v5 (37 modules)
        self.assertEqual(adaptive_grid_size(60), 4)   # v8 (49 modules)
        self.assertEqual(adaptive_grid_size(68), 5)   # v10 (57 modules)
        self.assertEqual(adaptive_grid_size(76), 5)   # v13 (69 modules)

    def test_zone_bounds_even_split(self):
        """When S is divisible by N, zones are equally sized."""
        # S=28, N=2: each zone is 14 wide
        self.assertEqual(zone_bounds(28, 2, 0, 0), (0, 0, 14, 14))
        self.assertEqual(zone_bounds(28, 2, 0, 1), (0, 14, 14, 28))
        self.assertEqual(zone_bounds(28, 2, 1, 0), (14, 0, 28, 14))
        self.assertEqual(zone_bounds(28, 2, 1, 1), (14, 14, 28, 28))

    def test_zone_bounds_remainder_absorbed_by_edge(self):
        """When S is not divisible by N, the last row/column zone is wider."""
        # S=44, N=3: floor(44/3) = 14; first two zones are 14, last is 16
        self.assertEqual(zone_bounds(44, 3, 0, 0), (0, 0, 14, 14))
        self.assertEqual(zone_bounds(44, 3, 0, 1), (0, 14, 14, 28))
        self.assertEqual(zone_bounds(44, 3, 0, 2), (0, 28, 14, 44))
        self.assertEqual(zone_bounds(44, 3, 2, 2), (28, 28, 44, 44))

    def test_module_at_reads_packed_bits(self):
        """module_at reads a single bit from the qrcode.encode() output buffer.

        The buffer is packed left-to-right, top-to-bottom; bit 0 is the
        MSB of byte 0.
        """
        # 8x8 bitmap: row 0 = 0b10000000, row 1 = 0b01000000, ...
        # so module_at(buf, 8, r, c) == 1 iff r == c
        buf = bytearray(b"\x80\x40\x20\x10\x08\x04\x02\x01")
        for r in range(8):
            for c in range(8):
                self.assertEqual(
                    module_at(buf, 8, r, c),
                    1 if r == c else 0,
                    "module_at mismatch at (%d, %d)" % (r, c),
                )

    def test_next_zone_clamps_at_edges(self):
        """Direction strings move (r, c); past-edge moves are no-ops."""
        # interior — moves freely
        self.assertEqual(next_zone(4, 1, 1, "up"),    (0, 1))
        self.assertEqual(next_zone(4, 1, 1, "down"),  (2, 1))
        self.assertEqual(next_zone(4, 1, 1, "left"),  (1, 0))
        self.assertEqual(next_zone(4, 1, 1, "right"), (1, 2))
        # at edges — clamped
        self.assertEqual(next_zone(4, 0, 0, "up"),    (0, 0))
        self.assertEqual(next_zone(4, 0, 0, "left"),  (0, 0))
        self.assertEqual(next_zone(4, 3, 3, "down"),  (3, 3))
        self.assertEqual(next_zone(4, 3, 3, "right"), (3, 3))

    def test_iter_zone_modules_full_diagonal(self):
        """Generator yields (zone_row, zone_col, is_dark) for each module."""
        # 8x8 bitmap with bit set iff r == c: 0x80 0x40 0x20 0x10 ...
        raw = bytearray(b"\x80\x40\x20\x10\x08\x04\x02\x01")
        # Zone (0, 0) of a 2x2 grid: top-left 4x4, diagonal r==c
        triples = list(iter_zone_modules(raw, 8, 2, 0, 0))
        self.assertEqual(len(triples), 16)
        for zr, zc, dark in triples:
            expected = 1 if zr == zc else 0
            self.assertEqual(dark, expected,
                             "mismatch at zone (%d, %d)" % (zr, zc))

    def test_iter_zone_modules_uneven_last_zone(self):
        """Remainder is absorbed by the last zone; iterator yields zone_h*zone_w items."""
        # s=44, n=3: floor(44/3)=14, last column/row absorbs remainder of 2.
        # Zone (2, 2): rows 28..44 (16), cols 28..44 (16) -> 256 items.
        raw = bytes(44 * 44 // 8)
        triples = list(iter_zone_modules(raw, 44, 3, 2, 2))
        self.assertEqual(len(triples), 16 * 16)
        # Zone (0, 2): rows 0..14, cols 28..44 -> 14*16 = 224 items.
        triples = list(iter_zone_modules(raw, 44, 3, 0, 2))
        self.assertEqual(len(triples), 14 * 16)

    def test_clamp_zone(self):
        """Clamp zone (r, c) to [0, n-1]; in-range values pass through."""
        # In-range -> unchanged
        self.assertEqual(clamp_zone(3, 0, 0), (0, 0))
        self.assertEqual(clamp_zone(3, 2, 1), (2, 1))
        # Out-of-range -> clamped to n-1
        self.assertEqual(clamp_zone(3, 4, 4), (2, 2))
        self.assertEqual(clamp_zone(2, 5, 0), (1, 0))
        self.assertEqual(clamp_zone(6, 5, 5), (5, 5))  # in-range edge

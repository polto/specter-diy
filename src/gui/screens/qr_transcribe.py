import lvgl as lv
import math
import qrcode

from .screen import Screen
from ..common import add_label, add_button, HOR_RES
from ..decorators import on_release
from qr_transcribe_logic import (
    adaptive_grid_size, iter_zone_modules, next_zone, zone_bounds, clamp_zone,
)


BTNSIZE = 50
NAV_Y_CENTER = 600
DPAD_CENTER_X = 135
MINIMAP_CENTER_X = 340
MINIMAP_CELL = 12
MINIMAP_GAP = 2
ZONE_AREA_SIDE = 400
ZONE_AREA_Y = 130
N_MIN = 2
N_MAX = 6
N_BTN_SIZE = 50


class QRTranscribeScreen(Screen):
    """Full-screen view that zooms into one zone of a QR code at a time.

    Used for hand-transcribing seed-class QRs onto paper. Each module of
    the zone is drawn as a small lv.obj coloured black (dark module) or
    white (light module) inside a fixed 400x400 container. Axis labels
    along the top + left make the row/col coordinates explicit.
    """

    def __init__(self, qr_text):
        super().__init__()
        self._qr_text = qr_text
        self._raw = bytearray(qrcode.encode(qr_text))
        self._s = int(math.sqrt(len(self._raw) * 8))
        self._n = adaptive_grid_size(self._s)
        self._zone_r = 0
        self._zone_c = 0

        self.title = add_label("Transcribe", scr=self, style="title")
        self.zone_label = add_label("", scr=self, style="hint")
        self.zone_label.align(self.title, lv.ALIGN.OUT_BOTTOM_MID, 0, 5)

        # Cell + label styles. Allocated once, reused across renders.
        self._dark_style = lv.style_t()
        self._dark_style.body.main_color = lv.color_make(0x00, 0x00, 0x00)
        self._dark_style.body.grad_color = lv.color_make(0x00, 0x00, 0x00)
        self._dark_style.body.opa = lv.OPA.COVER
        self._dark_style.body.radius = 0
        self._dark_style.body.border.width = 0

        self._light_style = lv.style_t()
        self._light_style.body.main_color = lv.color_make(0xFF, 0xFF, 0xFF)
        self._light_style.body.grad_color = lv.color_make(0xFF, 0xFF, 0xFF)
        self._light_style.body.opa = lv.OPA.COVER
        self._light_style.body.radius = 0
        self._light_style.body.border.width = 0

        self._bg_style = lv.style_t()
        self._bg_style.body.main_color = lv.color_make(0xFF, 0xFF, 0xFF)
        self._bg_style.body.grad_color = lv.color_make(0xFF, 0xFF, 0xFF)
        self._bg_style.body.opa = lv.OPA.COVER
        self._bg_style.body.radius = 0
        self._bg_style.body.border.width = 0

        self._label_style = lv.style_t()
        lv.style_copy(self._label_style, lv.style_plain)
        self._label_style.text.color = lv.color_make(0x00, 0x00, 0x00)
        self._label_style.body.opa = lv.OPA.TRANSP

        # White background pane that holds the cells. Rebuilt by _render_zone.
        self._zone_container = None

        self.btn_n_dec = lv.btn(self)
        lv.label(self.btn_n_dec).set_text("-")
        self.btn_n_dec.set_size(N_BTN_SIZE, N_BTN_SIZE)
        self.btn_n_dec.set_pos(20, 10)
        self.btn_n_dec.set_event_cb(on_release(lambda: self._change_n(-1)))

        self.btn_n_inc = lv.btn(self)
        lv.label(self.btn_n_inc).set_text("+")
        self.btn_n_inc.set_size(N_BTN_SIZE, N_BTN_SIZE)
        self.btn_n_inc.set_pos(HOR_RES - 20 - N_BTN_SIZE, 10)
        self.btn_n_inc.set_event_cb(on_release(lambda: self._change_n(+1)))

        self.n_label = add_label("", scr=self, style="hint")
        self.n_label.align(self.btn_n_dec, lv.ALIGN.OUT_BOTTOM_MID, 0, 5)

        self._create_arrows()
        self._create_minimap()
        self._render_zone()

        self.close_button = add_button(
            "Done",
            on_release(lambda: self.set_value(None)),
            scr=self,
            y=720,
        )

    def _create_arrows(self):
        self.btn_up = lv.btn(self)
        lv.label(self.btn_up).set_text(lv.SYMBOL.UP)
        self.btn_up.set_size(BTNSIZE, BTNSIZE)
        self.btn_up.set_event_cb(on_release(lambda: self._move("up")))

        self.btn_down = lv.btn(self)
        lv.label(self.btn_down).set_text(lv.SYMBOL.DOWN)
        self.btn_down.set_size(BTNSIZE, BTNSIZE)
        self.btn_down.set_event_cb(on_release(lambda: self._move("down")))

        self.btn_left = lv.btn(self)
        lv.label(self.btn_left).set_text(lv.SYMBOL.LEFT)
        self.btn_left.set_size(BTNSIZE, BTNSIZE)
        self.btn_left.set_event_cb(on_release(lambda: self._move("left")))

        self.btn_right = lv.btn(self)
        lv.label(self.btn_right).set_text(lv.SYMBOL.RIGHT)
        self.btn_right.set_size(BTNSIZE, BTNSIZE)
        self.btn_right.set_event_cb(on_release(lambda: self._move("right")))

        self.btn_up.set_pos(DPAD_CENTER_X - BTNSIZE // 2, NAV_Y_CENTER - BTNSIZE - 5)
        self.btn_down.set_pos(DPAD_CENTER_X - BTNSIZE // 2, NAV_Y_CENTER + BTNSIZE + 5)
        self.btn_left.set_pos(DPAD_CENTER_X - BTNSIZE * 3 // 2 - 5, NAV_Y_CENTER - BTNSIZE // 2)
        self.btn_right.set_pos(DPAD_CENTER_X + BTNSIZE // 2 + 5, NAV_Y_CENTER - BTNSIZE // 2)

    def _create_minimap(self):
        size = self._n * MINIMAP_CELL + (self._n - 1) * MINIMAP_GAP
        self._minimap_container = lv.obj(self)
        self._minimap_container.set_size(size, size)
        self._minimap_container.set_pos(
            MINIMAP_CENTER_X - size // 2, NAV_Y_CENTER - size // 2
        )
        self._mm_active_style = lv.style_t()
        self._mm_active_style.body.main_color = lv.color_hex(0x3B82F6)
        self._mm_active_style.body.grad_color = lv.color_hex(0x3B82F6)
        self._mm_active_style.body.opa = 255
        self._mm_inactive_style = lv.style_t()
        self._mm_inactive_style.body.main_color = lv.color_hex(0xDDDDDD)
        self._mm_inactive_style.body.grad_color = lv.color_hex(0xDDDDDD)
        self._mm_inactive_style.body.opa = 255
        self._minimap_cells = []
        for r in range(self._n):
            row = []
            for c in range(self._n):
                cell = lv.obj(self._minimap_container)
                cell.set_size(MINIMAP_CELL, MINIMAP_CELL)
                cell.set_pos(
                    c * (MINIMAP_CELL + MINIMAP_GAP),
                    r * (MINIMAP_CELL + MINIMAP_GAP),
                )
                row.append(cell)
            self._minimap_cells.append(row)

    def _update_minimap(self):
        for r in range(self._n):
            for c in range(self._n):
                style = (self._mm_active_style
                         if (r == self._zone_r and c == self._zone_c)
                         else self._mm_inactive_style)
                self._minimap_cells[r][c].set_style(style)

    def _update_button_states(self):
        for btn, ok in (
            (self.btn_up,    self._zone_r > 0),
            (self.btn_down,  self._zone_r < self._n - 1),
            (self.btn_left,  self._zone_c > 0),
            (self.btn_right, self._zone_c < self._n - 1),
            (self.btn_n_dec, self._n > N_MIN),
            (self.btn_n_inc, self._n < N_MAX),
        ):
            btn.set_state(lv.btn.STATE.REL if ok else lv.btn.STATE.INA)

    def _render_zone(self):
        # Tear down the previous zone subtree so a stale grid never lingers.
        if self._zone_container is not None:
            self._zone_container.delete()
        self._zone_container = lv.obj(self)
        self._zone_container.set_style(self._bg_style)
        self._zone_container.set_size(ZONE_AREA_SIDE, ZONE_AREA_SIDE)
        self._zone_container.align(self, lv.ALIGN.IN_TOP_MID, 0, ZONE_AREA_Y)

        r0, c0, r1, c1 = zone_bounds(self._s, self._n, self._zone_r, self._zone_c)
        zone_h = r1 - r0
        zone_w = c1 - c0
        # Reserve one cell-width along the top + left edges for axis numbers.
        cell = ZONE_AREA_SIDE // (max(zone_h, zone_w) + 1)
        grid_w = zone_w * cell
        grid_h = zone_h * cell
        ox = (ZONE_AREA_SIDE - grid_w + cell) // 2
        oy = (ZONE_AREA_SIDE - grid_h + cell) // 2

        # Column numbers along the top: absolute QR column index (1..s).
        for zc in range(zone_w):
            lbl = lv.label(self._zone_container)
            lbl.set_style(0, self._label_style)
            lbl.set_text(str(c0 + zc + 1))
            lbl.set_size(cell, cell)
            lbl.set_pos(ox + zc * cell, oy - cell)
            lbl.set_align(lv.label.ALIGN.CENTER)

        # Row numbers along the left: absolute QR row index (1..s).
        for zr in range(zone_h):
            lbl = lv.label(self._zone_container)
            lbl.set_style(0, self._label_style)
            lbl.set_text(str(r0 + zr + 1))
            lbl.set_size(cell, cell)
            lbl.set_pos(ox - cell, oy + zr * cell + (cell // 4))
            lbl.set_align(lv.label.ALIGN.CENTER)

        # Module cells: one lv.obj per module. Each gets a 1px gap on each
        # side via (cell - 2) sizing so adjacent dark modules show as
        # discrete dots, not a connected blob.
        for zr, zc, dark in iter_zone_modules(
            self._raw, self._s, self._n, self._zone_r, self._zone_c
        ):
            obj = lv.obj(self._zone_container)
            obj.set_size(cell - 2, cell - 2)
            obj.set_pos(ox + zc * cell + 1, oy + zr * cell + 1)
            obj.set_style(self._dark_style if dark else self._light_style)

        self.zone_label.set_text(
            "Row %d, Col %d of %dx%d"
            % (self._zone_r + 1, self._zone_c + 1, self._n, self._n)
        )
        self.n_label.set_text("N = %d" % self._n)
        self._update_minimap()
        self._update_button_states()

    def _move(self, direction):
        new_r, new_c = next_zone(self._n, self._zone_r, self._zone_c, direction)
        if (new_r, new_c) == (self._zone_r, self._zone_c):
            return
        self._zone_r, self._zone_c = new_r, new_c
        self._render_zone()

    def _change_n(self, delta):
        new_n = self._n + delta
        if new_n < N_MIN or new_n > N_MAX:
            return
        self._n = new_n
        self._zone_r, self._zone_c = clamp_zone(self._n, self._zone_r, self._zone_c)
        # Rebuild minimap (its grid size changes with N).
        self._minimap_container.delete()
        self._create_minimap()
        self._render_zone()

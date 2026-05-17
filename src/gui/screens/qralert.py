import asyncio
import lvgl as lv

from .alert import Alert
from .qr_transcribe import QRTranscribeScreen
from ..common import add_qrcode, add_button
from ..decorators import on_release


class QRAlert(Alert):
    def __init__(
        self,
        title="QR Alert!",
        message="Something happened",
        qr_message=None,
        qr_width=None,
        button_text="Close",
        note=None,
        transcribe=False,
    ):
        if qr_message is None:
            qr_message = message
        super().__init__(title, message, button_text, note=note)
        self.qr = add_qrcode(qr_message, scr=self, width=qr_width)
        self.qr.align(self.page, lv.ALIGN.IN_TOP_MID, 0, 20)
        self.message.align(self.qr, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        if transcribe:
            btn = add_button("Transcribe", on_release(self._open_transcribe), scr=self)
            btn.align(self.message, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)

    def _open_transcribe(self):
        asyncio.create_task(self._transcribe_loop())

    async def _transcribe_loop(self):
        # qr.get_text() returns the original payload (not the bcur-frame text)
        scr = QRTranscribeScreen(self.qr.get_text())
        lv.scr_load(scr)
        try:
            await scr.result()
        finally:
            lv.scr_load(self)
            scr.del_async()

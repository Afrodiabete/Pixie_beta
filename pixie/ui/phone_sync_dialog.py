"""「手機同步」視窗：開關同步、顯示配對 QR code、同步狀態。"""
from __future__ import annotations

import io

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QVBoxLayout)

from ..sync.phone_sync import PhoneSync


def _qr_pixmap(text: str, size: int = 240) -> QPixmap:
    import segno

    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="png", scale=8, border=2)
    pix = QPixmap()
    pix.loadFromData(buf.getvalue(), "PNG")
    return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.FastTransformation)


class PhoneSyncDialog(QDialog):
    def __init__(self, sync: PhoneSync, parent=None):
        super().__init__(parent)
        self.sync = sync
        self.setWindowTitle("手機同步")
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(320)

        self.enable = QCheckBox("把待辦同步到手機")
        self.enable.setChecked(sync.enabled)
        self.enable.toggled.connect(self._toggle)

        self.hint = QLabel("打開手機上的「小精靈」app，按「掃描配對 QR code」掃這個：", wordWrap=True)
        self.qr = QLabel(alignment=Qt.AlignCenter)
        self.status = QLabel(sync.status, wordWrap=True)
        self.status.setStyleSheet("color:#7a6a90;")
        sync.status_changed.connect(self.status.setText)

        self.btn_sync = QPushButton("立即同步", clicked=sync.push_now)
        self.btn_copy = QPushButton("複製配對連結", clicked=self._copy)
        self.btn_reset = QPushButton("重新產生金鑰", clicked=self._reset)
        btns = QHBoxLayout()
        for b in (self.btn_sync, self.btn_copy, self.btn_reset):
            btns.addWidget(b)

        note = QLabel("待辦內容以 AES-256 加密後經 ntfy.sh 中繼，金鑰只存在這台電腦與你的手機。"
                      "QR code 等同金鑰，請勿分享。", wordWrap=True)
        note.setStyleSheet("color:#9b8bb0; font-size:11px;")

        lay = QVBoxLayout(self)
        for w in (self.enable, self.hint, self.qr, self.status):
            lay.addWidget(w)
        lay.addLayout(btns)
        lay.addWidget(note)
        self._refresh()

    def _refresh(self) -> None:
        on = self.sync.enabled
        for w in (self.hint, self.qr, self.btn_sync, self.btn_copy, self.btn_reset):
            w.setVisible(on)
        if on:
            self.qr.setPixmap(_qr_pixmap(self.sync.pairing_uri()))
        self.adjustSize()

    def _toggle(self, on: bool) -> None:
        self.sync.set_enabled(on)
        self._refresh()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.sync.pairing_uri())
        self.status.setText("已複製配對連結，可以傳到手機後在 app 裡貼上。")

    def _reset(self) -> None:
        ok = QMessageBox.question(self, "重新產生金鑰",
                                  "已配對的手機將無法再收到同步，需要重新掃描。確定嗎？")
        if ok == QMessageBox.Yes:
            self.sync.reset_credentials()
            self._refresh()
            self.sync.push_now()

"""桌面腳色本體：透明、無邊框、置頂的小視窗，預設停在螢幕右下角。

外觀依狀態切換，圖檔對應寫在 config.json 的 character.sprites：
    default  平時 / 正常回話
    thinking 等待 LLM 回覆
    tea_time 喝水提醒
    angry    有待辦事項逾期未完成
    poke       點開對話框時（短暫反應）
    speechless 在對話框輸入送出後（短暫反應）
另外 sprites.blink 是 default 的閉眼版：待機（default）時每隔幾秒換上一下，看起來像在眨眼。
找不到某狀態的圖時會退回 default；連 default 都沒有就畫一個佔位腳色。
"""
from __future__ import annotations

import math
import random
import time
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QMouseEvent, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget


class State(Enum):
    DEFAULT = "default"
    THINKING = "thinking"
    TEA_TIME = "tea_time"
    ANGRY = "angry"
    POKE = "poke"
    SPEECHLESS = "speechless"


def load_pixmap(path: Path) -> QPixmap:
    """先用 Qt 讀；Qt 不支援的格式（例如沒有 webp 外掛時）改用 Pillow。"""
    pix = QPixmap(str(path))
    if not pix.isNull():
        return pix
    try:
        from PIL import Image
    except ImportError:
        print(f"[character] 無法讀取 {path.name}：Qt 不支援此格式且未安裝 Pillow")
        return QPixmap()
    with Image.open(path) as im:
        im = im.convert("RGBA")
        data = im.tobytes("raw", "RGBA")
        img = QImage(data, im.width, im.height, im.width * 4, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(img)


class CharacterWidget(QWidget):
    clicked = Signal()
    menu_requested = Signal(QPoint)
    moved = Signal()

    def __init__(self, cfg: dict, root: Path):
        super().__init__()
        self.cfg = cfg
        self.size_px = int(cfg.get("size", 160))
        self.state = State.DEFAULT
        self._t = 0.0
        self._blink = 0                      # 剩幾幀維持閉眼
        self._next_blink = time.monotonic() + self._blink_interval()   # 用真實時間：電腦忙、掉幀時也照常眨眼
        self._drag_origin: QPoint | None = None
        self._drag_moved = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.size_px, self.size_px)
        self.setCursor(Qt.PointingHandCursor)

        sprite_dir = root / cfg.get("sprite_dir", "assets/character")
        self.sprites = self._load_sprites(sprite_dir, cfg.get("sprites", {}))
        self.blink_sprite = self._load_one(sprite_dir / cfg.get("sprites", {}).get("blink", "default_blink.webp"))

        self._timer = QTimer(self, interval=33, timeout=self._tick)  # ~30 FPS
        self._timer.start()
        self.move_to_corner()

    # ---------- 位置 ----------
    def move_to_corner(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()  # 扣掉工作列
        m = int(self.cfg.get("margin", 16))
        self.move(screen.right() - self.width() - m, screen.bottom() - self.height() - m)

    # ---------- 狀態 ----------
    def set_state(self, state: State) -> None:
        if state != self.state:
            self.state = state
            self.update()

    @staticmethod
    def _blink_interval() -> float:
        return random.uniform(2.5, 6.0)      # 人大約每 3~5 秒眨一次眼

    def _tick(self) -> None:
        self._t += 0.033
        if self._blink > 0:
            self._blink -= 1
        elif time.monotonic() >= self._next_blink:
            self._blink = 4                  # 約 0.13 秒
            # 偶爾連眨兩下
            self._next_blink = time.monotonic() + (0.3 if random.random() < 0.15 else self._blink_interval())
        self.update()

    # ---------- 圖檔 ----------
    def _load_sprites(self, folder: Path, mapping: dict) -> dict[State, QPixmap]:
        out: dict[State, QPixmap] = {}
        for st in State:
            filename = mapping.get(st.value, f"{st.value}.png")
            pix = self._load_one(folder / filename)
            if pix:
                out[st] = pix
        return out

    def _load_one(self, path: Path) -> QPixmap | None:
        if not path.exists():
            return None
        pix = load_pixmap(path)
        if pix.isNull():
            return None
        return pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 先縮放好，避免每一幀重新縮放

    def current_pixmap(self) -> QPixmap | None:
        if self._blink and self.state == State.DEFAULT and self.blink_sprite and State.DEFAULT in self.sprites:
            return self.blink_sprite
        return self.sprites.get(self.state) or self.sprites.get(State.DEFAULT)

    # ---------- 繪製 ----------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bob = math.sin(self._t * 2.2) * 3  # 呼吸上下浮動

        pix = self.current_pixmap()
        if pix:
            p.drawPixmap((self.width() - pix.width()) // 2,
                         (self.height() - pix.height()) // 2 + int(bob), pix)
        else:
            self._paint_placeholder(p, bob)

        # 沒有專屬圖時，用小圓點表示狀態
        if self.state == State.THINKING and State.THINKING not in self.sprites:
            self._paint_think_dots(p)
        p.end()

    def _paint_placeholder(self, p: QPainter, bob: float) -> None:
        s = self.size_px
        cx, cy = s / 2, s * 0.58 + bob
        r = s * 0.34

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QPointF(s / 2, s * 0.94), r * 0.8, r * 0.14)

        p.setBrush(QColor("#f4e3ff"))
        p.setPen(QColor("#9b7bc4"))
        p.drawEllipse(QPointF(cx, cy), r, r * 0.92)

        hair = QPainterPath(QPointF(cx, cy - r * 0.9))
        hair.cubicTo(cx + r * 0.1, cy - r * 1.4, cx + r * 0.5, cy - r * 1.3, cx + r * 0.35, cy - r * 1.05)
        p.setBrush(Qt.NoBrush)
        p.drawPath(hair)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3d2b56"))
        ex, ey = r * 0.38, cy - r * 0.12
        eye_h = r * 0.04 if self._blink else r * 0.17
        for dx in (-ex, ex):
            p.drawEllipse(QPointF(cx + dx, ey), r * 0.1, eye_h)

        p.setBrush(QColor(255, 140, 170, 110))
        for dx in (-r * 0.62, r * 0.62):
            p.drawEllipse(QPointF(cx + dx, cy + r * 0.12), r * 0.13, r * 0.07)

        p.setPen(QColor("#c0506e"))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(cx - r * 0.12, cy + r * 0.12, r * 0.24, r * 0.18), 200 * 16, 140 * 16)

    def _paint_think_dots(self, p: QPainter) -> None:
        p.setPen(Qt.NoPen)
        for i in range(3):
            alpha = int(120 + 135 * max(0.0, math.sin(self._t * 5 - i * 0.8)))
            p.setBrush(QColor(155, 123, 196, alpha))
            p.drawEllipse(QPointF(self.width() * (0.62 + i * 0.1), self.height() * 0.12), 5, 5)

    # ---------- 滑鼠：左鍵點擊、拖曳移動、右鍵選單 ----------
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_origin = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_moved = False
        elif e.button() == Qt.RightButton:
            self.menu_requested.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_origin is not None and e.buttons() & Qt.LeftButton:
            new_pos = e.globalPosition().toPoint() - self._drag_origin
            if (new_pos - self.pos()).manhattanLength() > 3:
                self._drag_moved = True
            if self._drag_moved:
                self.move(new_pos)
                self.moved.emit()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            if not self._drag_moved:
                self.clicked.emit()
            self._drag_origin = None

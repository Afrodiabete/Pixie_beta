"""產生小精靈的所有美術素材（原創、純程式繪製）。

    python tools/draw_art.py

輸出：
  assets/character/*.webp           桌面腳色 7 種外觀（340x340）
  assets/background/card.webp       對話框背景（840x400）
  android/.../drawable-nodpi/*.png  手機 app 用的腳色圖
  android/.../mipmap-*/ic_launcher.png  手機 app 圖示
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
S = 4            # 超取樣倍率，畫大再縮小 = 平滑邊緣
W = H = 340

LINE = (58, 74, 60, 255)
SKIN = (255, 236, 222, 255)
HAIR = (128, 204, 150, 255)
HAIR_DARK = (92, 168, 116, 255)
HAIR_LIGHT = (176, 230, 186, 255)
EYE = (46, 110, 84, 255)
EYE_DARK = (28, 70, 54, 255)
BLUSH = (255, 160, 170, 110)
DRESS = (110, 190, 130, 255)
DRESS_DARK = (80, 150, 100, 255)
WING = (200, 240, 255, 150)
WING_EDGE = (120, 190, 220, 220)
PETAL = (255, 190, 210, 255)
PETAL_C = (255, 220, 110, 255)
RED = (220, 70, 70, 255)
WATER = (120, 200, 255, 230)


def s(*v):
    return [x * S for x in v]


def ell(d, cx, cy, rx, ry, fill, outline=LINE, w=3):
    d.ellipse(s(cx - rx, cy - ry, cx + rx, cy + ry), fill=fill, outline=outline, width=w * S if outline else 0)


def poly(d, pts, fill, outline=LINE, w=3):
    p = [(x * S, y * S) for x, y in pts]
    d.polygon(p, fill=fill)
    if outline:
        d.line(p + [p[0]], fill=outline, width=w * S, joint="curve")


def arc(d, cx, cy, rx, ry, a0, a1, w=3, color=LINE):
    d.arc(s(cx - rx, cy - ry, cx + rx, cy + ry), a0, a1, fill=color, width=w * S)


def line(d, pts, w=3, color=LINE):
    d.line([(x * S, y * S) for x, y in pts], fill=color, width=w * S, joint="curve")
    for x, y in (pts[0], pts[-1]):   # 圓頭線端
        r = w * S / 2
        d.ellipse((x * S - r, y * S - r, x * S + r, y * S + r), fill=color)


def leaf(d, cx, cy, length, width, angle, fill, outline=LINE, vein=True):
    pts = []
    for i in range(25):
        t = i / 24
        pts.append((t * length, math.sin(t * math.pi) * width / 2))
    for i in range(24, -1, -1):
        t = i / 24
        pts.append((t * length, -math.sin(t * math.pi) * width / 2))
    ca, sa = math.cos(angle), math.sin(angle)
    rot = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]
    poly(d, rot, fill, outline, 2)
    if vein:
        line(d, [(cx, cy), (cx + length * 0.8 * ca, cy + length * 0.8 * sa)], 1, outline)


def flower(d, cx, cy, r):
    for k in range(5):
        a = k * 2 * math.pi / 5 - math.pi / 2
        ell(d, cx + math.cos(a) * r, cy + math.sin(a) * r, r * 0.75, r * 0.75, PETAL, w=2)
    ell(d, cx, cy, r * 0.55, r * 0.55, PETAL_C, w=2)


def sparkle(d, cx, cy, r, color=(255, 230, 120, 255)):
    pts = []
    for k in range(8):
        a = k * math.pi / 4 - math.pi / 2
        rr = r if k % 2 == 0 else r * 0.3
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    poly(d, pts, color, None)


def wings(img):
    layer = Image.new("RGBA", img.size)
    d = ImageDraw.Draw(layer)
    for side in (-1, 1):
        # 上翅
        cx, cy = 170 + side * 108, 175
        ell(d, cx, cy, 62, 44, WING, WING_EDGE, 3)
        line(d, [(170 + side * 60, 195), (cx + side * 20, cy - 10)], 2, WING_EDGE)
        # 下翅
        cx2, cy2 = 170 + side * 88, 245
        ell(d, cx2, cy2, 40, 30, WING, WING_EDGE, 3)
    img.alpha_composite(layer)


def body(d, tea=False):
    # 裙子（葉片形）
    poly(d, [(128, 262), (212, 262), (234, 324), (106, 324)], DRESS)
    for x in (120, 150, 180, 210):
        leaf(d, x + 10, 322, 15, 14, math.pi / 2 + (x - 165) / 200, DRESS_DARK, vein=False)
    # 手臂
    if tea:
        ell(d, 140, 292, 13, 12, SKIN)
        ell(d, 200, 292, 13, 12, SKIN)
    else:
        ell(d, 122, 290, 12, 14, SKIN)
        ell(d, 218, 290, 12, 14, SKIN)
    # 領口小葉
    leaf(d, 170, 262, 26, 16, math.pi * 0.85, HAIR_LIGHT, vein=False)
    leaf(d, 170, 262, 26, 16, math.pi * 0.15, HAIR_LIGHT, vein=False)


def head(d):
    # 後髮
    ell(d, 170, 150, 112, 106, HAIR)
    # 尖耳朵
    for side in (-1, 1):
        x = 170 + side * 96
        poly(d, [(x - side * 6, 150), (x + side * 40, 118), (x - side * 4, 186)], SKIN)
    # 臉
    ell(d, 170, 168, 88, 80, SKIN)
    # 瀏海：一排圓弧
    bang = [(96, 120, 34), (126, 104, 32), (158, 98, 32), (190, 100, 32), (222, 108, 32), (248, 126, 30)]
    for x, y, r in bang:
        d.pieslice(s(x - r, y - r, x + r, y + r), 0, 180, fill=HAIR)
    ell(d, 170, 92, 96, 42, HAIR, None)
    arc(d, 170, 150, 112, 106, 200, 340, 3)
    for x, y, r in bang:
        arc(d, x, y, r, r, 20, 160, 3)
    # 頭髮高光
    arc(d, 150, 90, 50, 22, 200, 280, 4, HAIR_LIGHT)
    # 頭上嫩芽
    line(d, [(170, 52), (172, 34)], 3, LINE)
    leaf(d, 172, 36, 34, 18, -math.pi * 0.85, HAIR_LIGHT)
    leaf(d, 172, 36, 34, 18, -math.pi * 0.15, HAIR_LIGHT)
    # 花飾
    flower(d, 232, 86, 10)


def blush(img):
    layer = Image.new("RGBA", img.size)
    d = ImageDraw.Draw(layer)
    for x in (118, 222):
        d.ellipse(s(x - 16, 192, x + 16, 204), fill=BLUSH)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(3 * S)))


def eye_open(d, cx, cy, look=(0, 0), big=1.0):
    rx, ry = 15 * big, 20 * big
    ell(d, cx, cy, rx, ry, (255, 255, 255, 255), LINE, 3)
    ix, iy = cx + look[0], cy + look[1]
    ell(d, ix, iy + 2, rx * 0.78, ry * 0.8, EYE, None)
    ell(d, ix, iy + 4, rx * 0.4, ry * 0.42, EYE_DARK, None)
    ell(d, ix - 4, iy - 5, 4.5 * big, 5.5 * big, (255, 255, 255, 255), None)
    ell(d, ix + 5, iy + 9, 2, 2, (255, 255, 255, 255), None)
    arc(d, cx, cy - 2, rx + 2, ry + 2, 200, 340, 4)   # 上眼線


def eye_closed_happy(d, cx, cy):   # ^ ^
    line(d, [(cx - 13, cy + 4), (cx, cy - 7), (cx + 13, cy + 4)], 4)


def eye_closed(d, cx, cy):   # 閉眼弧線（眨眼）
    arc(d, cx, cy - 6, 15, 12, 20, 160, 4)


def eye_flat(d, cx, cy):     # 無言 —
    line(d, [(cx - 14, cy), (cx + 14, cy)], 4)


def face(img, kind):
    d = ImageDraw.Draw(img)
    L, R, Y = 132, 208, 172
    if kind == "default":
        eye_open(d, L, Y); eye_open(d, R, Y)
        arc(d, 170, 204, 10, 8, 20, 160, 3)
    elif kind == "blink":
        eye_closed(d, L, Y); eye_closed(d, R, Y)
        arc(d, 170, 204, 10, 8, 20, 160, 3)
    elif kind == "thinking":
        eye_open(d, L, Y, look=(4, -6)); eye_open(d, R, Y, look=(4, -6))
        line(d, [(164, 210), (178, 207)], 3)
        for i, (x, y, r) in enumerate([(262, 58, 5), (280, 40, 7), (302, 20, 9)]):
            ell(d, x, y, r, r, (255, 255, 255, 255), LINE, 2)
    elif kind == "tea":
        eye_closed_happy(d, L, Y); eye_closed_happy(d, R, Y)
        arc(d, 170, 202, 9, 7, 20, 160, 3)
    elif kind == "angry":
        eye_open(d, L, Y + 2, big=0.9); eye_open(d, R, Y + 2, big=0.9)
        line(d, [(114, 140), (148, 152)], 5)
        line(d, [(226, 140), (192, 152)], 5)
        arc(d, 170, 214, 11, 8, 200, 340, 3)
        # 生氣符號
        cx, cy = 92, 96
        for a in (0, 90, 180, 270):
            r = math.radians(a + 45)
            arc(d, cx + math.cos(r) * 10, cy + math.sin(r) * 10, 7, 7, a + 135 - 70, a + 135 + 70, 4, RED)
        # 鼓起的臉頰
        ell(d, 108, 200, 8, 6, (255, 175, 180, 255), None)
        ell(d, 232, 200, 8, 6, (255, 175, 180, 255), None)
    elif kind == "poke":
        eye_open(d, L, Y, big=1.12); eye_open(d, R, Y, big=1.12)
        ell(d, 170, 210, 7, 8, (200, 80, 90, 255), LINE, 3)
        for x, y, r in [(70, 70, 12), (276, 64, 10), (290, 120, 7), (52, 128, 7)]:
            sparkle(d, x, y, r)
    elif kind == "speechless":
        eye_flat(d, L, Y + 2); eye_flat(d, R, Y + 2)
        line(d, [(160, 208), (180, 208)], 3)
        # 汗滴
        poly(d, [(250, 118), (242, 138), (250, 146), (258, 138)], WATER, LINE, 2)


def tea_cup(d):
    # 橡實杯 + 水滴
    ell(d, 170, 296, 30, 24, (190, 140, 90, 255))
    d.chord(s(140, 262, 200, 302), 180, 360, fill=(140, 96, 60, 255), outline=LINE, width=3 * S)
    ell(d, 170, 280, 24, 6, WATER, LINE, 2)
    line(d, [(170, 262), (172, 254)], 3, (110, 80, 50, 255))
    for x, y in [(140, 248), (200, 244)]:
        poly(d, [(x, y - 10), (x - 6, y + 2), (x, y + 7), (x + 6, y + 2)], WATER, LINE, 2)


def character(kind):
    img = Image.new("RGBA", (W * S, H * S))
    wings(img)
    d = ImageDraw.Draw(img)
    body(d, tea=(kind == "tea"))
    head(d)
    blush(img)
    face(img, kind)
    if kind == "tea":
        tea_cup(ImageDraw.Draw(img))
    return img.resize((W, H), Image.LANCZOS)


def background():
    bw, bh = 840, 400
    img = Image.new("RGBA", (bw * S, bh * S), (238, 248, 236, 255))
    d = ImageDraw.Draw(img)
    # 柔和漸層
    for y in range(bh):
        t = y / bh
        c = (int(236 - 14 * t), int(248 - 6 * t), int(238 - 16 * t), 255)
        d.rectangle((0, y * S, bw * S, (y + 1) * S), fill=c)
    rnd = random.Random(7)
    soft = [(170, 220, 170, 255), (150, 205, 160, 255), (196, 232, 190, 255), (130, 190, 150, 255)]
    for _ in range(70):
        x, y = rnd.uniform(-20, bw + 20), rnd.uniform(-20, bh + 20)
        leaf(d, x, y, rnd.uniform(30, 70), rnd.uniform(16, 30), rnd.uniform(0, 2 * math.pi),
             rnd.choice(soft), outline=(120, 170, 130, 255), vein=True)
    for _ in range(16):
        flower(d, rnd.uniform(0, bw), rnd.uniform(0, bh), rnd.uniform(6, 11))
    for _ in range(30):
        sparkle(d, rnd.uniform(0, bw), rnd.uniform(0, bh), rnd.uniform(4, 9), (255, 244, 180, 255))
    img = img.filter(ImageFilter.GaussianBlur(1.2 * S))
    return img.resize((bw, bh), Image.LANCZOS)


def launcher(base: Image.Image, size: int) -> Image.Image:
    bg = Image.new("RGBA", (512, 512))
    ImageDraw.Draw(bg).ellipse((0, 0, 511, 511), fill=(226, 246, 228, 255))
    face_crop = base.crop((20, 0, 320, 300)).resize((440, 440), Image.LANCZOS)
    bg.alpha_composite(face_crop, (36, 44))
    mask = Image.new("L", (512, 512))
    ImageDraw.Draw(mask).ellipse((0, 0, 511, 511), fill=255)
    out = Image.new("RGBA", (512, 512))
    out.paste(bg, (0, 0), mask)
    return out.resize((size, size), Image.LANCZOS)


def main() -> None:
    char_dir = ROOT / "assets" / "character"
    char_dir.mkdir(parents=True, exist_ok=True)
    files = {"default": "default.webp", "blink": "default_blink.webp", "thinking": "thinking.webp",
             "tea": "tea time.webp", "angry": "angry.webp", "poke": "poke.webp",
             "speechless": "speechless.webp"}
    imgs = {}
    for kind, name in files.items():
        imgs[kind] = character(kind)
        imgs[kind].save(char_dir / name, lossless=True)

    bg_dir = ROOT / "assets" / "background"
    bg_dir.mkdir(parents=True, exist_ok=True)
    background().save(bg_dir / "card.webp", quality=90)

    res = ROOT / "android" / "app" / "src" / "main" / "res"
    (res / "drawable-nodpi").mkdir(parents=True, exist_ok=True)
    imgs["default"].save(res / "drawable-nodpi" / "pixie_default.png")
    imgs["angry"].save(res / "drawable-nodpi" / "pixie_angry.png")
    for dpi, size in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
        (res / f"mipmap-{dpi}").mkdir(parents=True, exist_ok=True)
        launcher(imgs["default"], size).save(res / f"mipmap-{dpi}" / "ic_launcher.png")
    print("done")


if __name__ == "__main__":
    main()

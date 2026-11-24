"""打包成 Windows exe（PyInstaller，資料夾版）。

    python tools/build_exe.py

輸出：dist/Pixie/Pixie.exe（整個 dist/Pixie 資料夾要一起帶走）
設定與資料存在 %APPDATA%\\Pixie，重新打包不會遺失。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
ICON = BUILD / "pixie.ico"

# 不需要、但 anaconda 環境裡有裝的大型套件；排除可大幅縮小體積
# PyQt5 必須排除，否則 PyInstaller 會因為同時偵測到兩套 Qt 而失敗
EXCLUDES = [
    "PyQt5", "PyQt6", "tkinter", "numpy", "pandas", "scipy", "matplotlib",
    "IPython", "jupyter", "notebook", "pytest", "sphinx", "sqlalchemy",
    # anthropic SDK 的 AWS / Google Cloud 支援（我們直連 Claude API，用不到）
    "boto3", "botocore", "google.auth", "google.cloud",
]


def make_icon() -> None:
    from PIL import Image

    BUILD.mkdir(exist_ok=True)
    with Image.open(ROOT / "assets" / "character" / "default.webp") as im:
        im.convert("RGBA").save(ICON, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def main() -> int:
    import PyInstaller.__main__

    make_icon()
    args = [
        str(ROOT / "main.py"),
        "--name", "Pixie",
        "--onedir",
        "--windowed",                      # 不開黑色主控台
        "--noconfirm",
        "--clean",
        "--icon", str(ICON),
        "--add-data", f"{ROOT / 'assets'};assets",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
        # anthropic 是在 factory 裡延遲匯入的，明確告訴 PyInstaller 要收進來
        "--hidden-import", "pixie.llm.anthropic_provider",
        "--hidden-import", "pixie.llm.openai_compatible_provider",
        "--hidden-import", "segno",
    ]
    for mod in EXCLUDES:
        args += ["--exclude-module", mod]

    PyInstaller.__main__.run(args)

    exe = ROOT / "dist" / "Pixie" / "Pixie.exe"
    if not exe.exists():
        print("❌ 打包失敗，找不到輸出的 exe")
        return 1
    size = sum(f.stat().st_size for f in exe.parent.rglob("*") if f.is_file()) / 1024 / 1024
    print(f"\n✅ 完成：{exe}\n   資料夾大小：{size:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

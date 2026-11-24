import sys


def self_test() -> int:
    """`Pixie.exe --self-test`：不開 UI，測試圖檔與 Claude 連線，結果寫到資料夾的 self_test.txt。
    打包後的 exe 沒有主控台，用這個確認 PyInstaller 有把需要的東西都收進去。"""
    from pixie.config import DATA_ROOT, RESOURCE_ROOT, load_config
    from pixie.llm import create_provider

    lines = [f"resource_root: {RESOURCE_ROOT}", f"data_root: {DATA_ROOT}"]
    sprites = sorted(p.name for p in (RESOURCE_ROOT / "assets" / "character").glob("*"))
    lines.append(f"sprites: {sprites}")
    try:
        from PIL import Image
        with Image.open(RESOURCE_ROOT / "assets" / "character" / "default.webp") as im:
            lines.append(f"webp decode: ok {im.size}")
    except Exception as e:
        lines.append(f"webp decode: FAIL {e!r}")

    cfg = load_config()
    provider, err = create_provider(cfg["llm"], cfg["character"]["persona"])
    lines.append(f"provider: {provider.name} {err}")
    if not err and provider.name != "mock":
        reply = "".join(provider.stream_chat([{"role": "user", "content": "用一句話打招呼"}]))
        lines.append(f"reply: {reply}")
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    (DATA_ROOT / "self_test.txt").write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    from pixie.app import main
    sys.exit(main())

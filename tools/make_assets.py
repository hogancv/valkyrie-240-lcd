"""生成 README 用的示意图（把示例各渲染一帧，拼成一张横图）。

    python tools/make_assets.py

产物：
  assets/hero.png                    四屏并排（测试卡 / 图片 / 实时面板 / Token 看板）
  assets/testcard-240.png
  assets/image-example-240.png
  assets/live-panel-240.png
  assets/token-board-240.png
  assets/token-board-240-3x.png      3 倍放大，README 里单独展示细节

Token 看板用 `--source auto`：本机装了 Token Monitor 就是真实数据，
没装则自动退回 demos/token-board/sample-data.json，保证任何机器都能出图。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

SIZE = 240


def load_module(filename: str, base: Path = ROOT / "examples"):
    spec = importlib.util.spec_from_file_location(
        "mod_" + filename.replace(".py", "").replace("-", "_"), base / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_image_example() -> Image.Image:
    """伪造一张「照片」示例：径向渐变 + 圆形，代表任意图片都能推。"""
    img = Image.new("RGB", (SIZE, SIZE))
    d = ImageDraw.Draw(img)
    for y in range(SIZE):
        for step in range(0, SIZE, 2):
            t = (y / SIZE) * 0.6 + (step / SIZE) * 0.4
            r = int(26 + 180 * t)
            g = int(40 + 90 * (1 - t))
            b = int(120 + 90 * (1 - t))
            d.rectangle((step, y, step + 1, y), fill=(r, g, b))
    d.ellipse((52, 52, 188, 188), fill=(255, 255, 255))
    d.ellipse((66, 66, 174, 174), fill=(24, 26, 34))
    d.ellipse((96, 96, 144, 144), fill=(255, 210, 90))
    d.text((10, SIZE - 22), "any PIL image", fill=(230, 232, 240))
    return img


def make_token_board() -> Image.Image:
    """作者本人在用的 Token 看板（真实数据优先，没有就演示数据）。"""
    render = load_module("render.py", ROOT / "demos" / "token-board")
    data = load_module("data.py", ROOT / "demos" / "token-board")
    return render.draw_board(data.load("auto"))


def compose(panels, gap=12, bg=(11, 13, 16)):
    w = len(panels) * SIZE + (len(panels) + 1) * gap
    h = SIZE + 2 * gap
    canvas = Image.new("RGB", (w, h), bg)
    for i, p in enumerate(panels):
        canvas.paste(p, (gap + i * (SIZE + gap), gap))
    return canvas


def main():
    ex1 = load_module("01_testcard.py")
    ex4 = load_module("04_live_panel.py")

    testcard = ex1.make_testcard(SIZE, SIZE, "V", "#0f1720")
    image_demo = make_image_example()

    # 固定一组假数据，让实时面板示意图里的数值稳定可复现
    ex4.collect_stats = lambda: {"cpu": 37.0, "mem": 62.0}
    live = ex4.draw_frame(SIZE, SIZE, "default")

    board = make_token_board()

    for name, img in (("testcard-240.png", testcard),
                      ("image-example-240.png", image_demo),
                      ("live-panel-240.png", live),
                      ("token-board-240.png", board)):
        img.save(ASSETS / name)
        print("[save] assets/%s" % name)

    board.resize((SIZE * 3, SIZE * 3), Image.NEAREST).save(ASSETS / "token-board-240-3x.png")
    print("[save] assets/token-board-240-3x.png")

    hero = compose([testcard, image_demo, live, board])
    hero.save(ASSETS / "hero.png")
    print("[save] assets/hero.png  (%dx%d)" % hero.size)


if __name__ == "__main__":
    main()

"""最简示例：画一张 240×240 的测试卡推上去，验证整条链路。

    python examples/01_testcard.py                # 推 8 秒
    python examples/01_testcard.py --seconds 30   # 推 30 秒
    python examples/01_testcard.py --letter B --bg "#101820"

屏上应该看到：白色边框 + 居中的大字母 + 底部标注 + 一圈彩色色条。
若出现「横向重复三次 + 下半空白」→ 像素格式被当成 RGB888 了（见 docs/PITFALLS.md）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from valkyrie_lcd import ValkyriePanel  # noqa: E402

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\bahnschrift.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size: int):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_testcard(width: int, height: int, letter: str = "A",
                  bg: str = "#1b2430") -> Image.Image:
    img = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(img)

    # 外框
    d.rectangle((0, 0, width - 1, height - 1), outline=(255, 255, 255), width=2)

    # 顶部色条：红 绿 蓝 白 黑
    bar_h = max(8, height // 20)
    colors = [(220, 40, 40), (30, 200, 90), (40, 90, 220),
              (240, 240, 240), (10, 10, 10)]
    seg = width // len(colors)
    for i, c in enumerate(colors):
        d.rectangle((i * seg, 2, (i + 1) * seg - 1, bar_h), fill=c)

    # 居中大字
    font = load_font(int(height * 0.55))
    bbox = d.textbbox((0, 0), letter, font=font)
    d.text(((width - (bbox[2] - bbox[0])) / 2 - bbox[0],
            (height - (bbox[3] - bbox[1])) / 2 - bbox[1] + bar_h / 2),
           letter, font=font, fill=(255, 255, 255))

    # 底部标注
    small = load_font(max(12, height // 16))
    label = "%dx%d testcard" % (width, height)
    bbox = d.textbbox((0, 0), label, font=small)
    d.text(((width - (bbox[2] - bbox[0])) / 2, height - bbox[3] - 10),
           label, font=small, fill=(150, 160, 175))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=240)
    ap.add_argument("--height", type=int, default=240)
    ap.add_argument("--letter", default="A")
    ap.add_argument("--bg", default="#1b2430")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--save", default=None, help="顺带把这帧存成 png")
    args = ap.parse_args()

    img = make_testcard(args.width, args.height, args.letter, args.bg)
    if args.save:
        img.save(args.save)
        print("[save] %s" % args.save)

    with ValkyriePanel(args.width, args.height) as panel:
        panel.stream([img], fps=args.fps, seconds=args.seconds)


if __name__ == "__main__":
    main()

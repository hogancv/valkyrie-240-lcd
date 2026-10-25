"""实时绘制：时钟 + 系统状态，展示「屏幕上想显示什么完全由你决定」。

    python examples/04_live_panel.py
    python examples/04_live_panel.py --seconds 60
    python examples/04_live_panel.py --style minimal

这一段是给 AI 的起点：把 draw_frame(now, stats) 换成任何东西，
就是在做你自己的副屏程序。psutil 是可选依赖，没装就只显示时钟。
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from valkyrie_lcd import ValkyriePanel  # noqa: E402

try:
    import psutil                                   # 可选
except ImportError:
    psutil = None

FONTS = [
    r"C:\Windows\Fonts\bahnschrift.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font(size: int):
    for p in FONTS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def collect_stats() -> dict:
    if psutil is None:
        return {}
    return {
        "cpu": psutil.cpu_percent(interval=None),
        "mem": psutil.virtual_memory().percent,
    }


def draw_frame(width: int, height: int, style: str = "default") -> Image.Image:
    now = dt.datetime.now()
    stats = collect_stats()

    if style == "minimal":
        img = Image.new("RGB", (width, height), (8, 8, 10))
        d = ImageDraw.Draw(img)
        f = font(int(height * 0.30))
        txt = now.strftime("%H:%M")
        bbox = d.textbbox((0, 0), txt, font=f)
        d.text(((width - (bbox[2] - bbox[0])) / 2, (height - (bbox[3] - bbox[1])) / 2 - bbox[1]),
               txt, font=f, fill=(240, 240, 245))
        return img

    img = Image.new("RGB", (width, height), (16, 18, 24))
    d = ImageDraw.Draw(img)

    # 顶部日期
    d.text((14, 12), now.strftime("%Y-%m-%d  %a"), font=font(14), fill=(120, 126, 140))

    # 大号时间
    f_time = font(int(height * 0.30))
    d.text((14, 32), now.strftime("%H:%M"), font=f_time, fill=(245, 247, 252))

    # 秒 + 进度条
    sec = now.second
    d.text((width - 46, 40), "%02d" % sec, font=font(20), fill=(90, 200, 255))
    bar_y = height - 74
    d.rectangle((14, bar_y, width - 14, bar_y + 5), fill=(38, 42, 52))
    d.rectangle((14, bar_y, 14 + int((width - 28) * sec / 60), bar_y + 5),
                fill=(90, 200, 255))

    # CPU / MEM
    y = bar_y - 52
    if stats:
        for label, key, color in (("CPU", "cpu", (255, 140, 90)),
                                  ("MEM", "mem", (120, 220, 160))):
            value = stats[key]
            d.text((14, y), label, font=font(13), fill=(140, 146, 160))
            d.text((width - 52, y - 3), "%3d%%" % value, font=font(15), fill=(230, 234, 242))
            d.rectangle((56, y + 4, width - 58, y + 9), fill=(38, 42, 52))
            d.rectangle((56, y + 4, 56 + int((width - 114) * value / 100), y + 9),
                        fill=color)
            y += 24
    else:
        d.text((14, y), "装 psutil 可显示 CPU/内存", font=font(12), fill=(110, 116, 130))

    return img


def frames(width: int, height: int, style: str):
    """惰性生成：每次被取一帧就重绘一次，时间/数据永远是新的。"""
    while True:
        yield draw_frame(width, height, style)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=240)
    ap.add_argument("--height", type=int, default=240)
    ap.add_argument("--style", choices=["default", "minimal"], default="default")
    ap.add_argument("--seconds", type=float, default=0, help="0 = 一直跑")
    ap.add_argument("--fps", type=float, default=2.0)
    args = ap.parse_args()

    if psutil is None:
        print("[warn] 未安装 psutil，只显示时钟（pip install psutil 可显示 CPU/内存）")

    with ValkyriePanel(args.width, args.height) as panel:
        try:
            panel.stream(frames(args.width, args.height, args.style),
                         fps=args.fps,
                         seconds=args.seconds if args.seconds > 0 else None)
        except KeyboardInterrupt:
            print("\n[info] 已停止")


if __name__ == "__main__":
    main()

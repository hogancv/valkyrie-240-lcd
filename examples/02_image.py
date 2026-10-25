"""推一张图片到屏上（等比裁切填满，不变形）。

    python examples/02_image.py photo.jpg
    python examples/02_image.py photo.jpg --fit contain   # 留黑边，不裁切
    python examples/02_image.py photo.jpg --seconds 0     # 0 = 一直显示
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from valkyrie_lcd import ValkyriePanel  # noqa: E402


def fit_image(img: Image.Image, width: int, height: int,
              mode: str = "cover", background=(0, 0, 0)) -> Image.Image:
    """cover = 裁切填满（默认）；contain = 等比缩小后留边。"""
    img = img.convert("RGB")
    src_ratio = img.width / img.height
    dst_ratio = width / height

    if mode == "contain":
        if src_ratio > dst_ratio:
            new_w, new_h = width, max(1, round(width / src_ratio))
        else:
            new_h, new_w = height, max(1, round(height * src_ratio))
        canvas = Image.new("RGB", (width, height), background)
        canvas.paste(img.resize((new_w, new_h), Image.LANCZOS),
                     ((width - new_w) // 2, (height - new_h) // 2))
        return canvas

    # cover
    if src_ratio > dst_ratio:
        new_h = height
        new_w = max(width, round(height * src_ratio))
    else:
        new_w = width
        new_h = max(height, round(width / src_ratio))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="图片路径（jpg/png/webp/bmp 都行）")
    ap.add_argument("--width", type=int, default=240)
    ap.add_argument("--height", type=int, default=240)
    ap.add_argument("--fit", choices=["cover", "contain"], default="cover")
    ap.add_argument("--seconds", type=float, default=0,
                    help="0 表示一直显示，Ctrl+C 退出")
    ap.add_argument("--fps", type=float, default=2.0)
    args = ap.parse_args()

    img = fit_image(Image.open(args.image), args.width, args.height, args.fit)
    with ValkyriePanel(args.width, args.height) as panel:
        if args.seconds <= 0:
            print("[info] 常驻显示，Ctrl+C 停止（面板会保留最后一帧）")
            try:
                panel.stream([img], fps=args.fps, seconds=None)
            except KeyboardInterrupt:
                pass
        else:
            panel.stream([img], fps=args.fps, seconds=args.seconds)


if __name__ == "__main__":
    main()

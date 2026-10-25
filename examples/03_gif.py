"""推 GIF 动画。

    python examples/03_gif.py cat.gif
    python examples/03_gif.py cat.gif --loops 3

GIF 的每帧时长不同，这里按各帧 duration 累加做时间轴同步，
而不是简单平均成固定 fps —— 否则动画节奏会跑偏。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageSequence  # noqa: E402

from valkyrie_lcd import ValkyriePanel  # noqa: E402


def load_gif(path: str, width: int, height: int):
    """返回 (帧列表, 各帧时长秒数)。"""
    im = Image.open(path)
    frames, durations = [], []
    for frame in ImageSequence.Iterator(im):
        rgb = frame.convert("RGB")
        # 等比缩放并居中留黑边，保住原动画构图
        ratio = min(width / rgb.width, height / rgb.height)
        new_size = (max(1, round(rgb.width * ratio)), max(1, round(rgb.height * ratio)))
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        canvas.paste(rgb.resize(new_size, Image.LANCZOS),
                     ((width - new_size[0]) // 2, (height - new_size[1]) // 2))
        frames.append(canvas)
        durations.append(frame.info.get("duration", 100) / 1000.0)
    return frames, durations


def play(panel: ValkyriePanel, frames, durations, loops: int = 0):
    """按每帧自己的时长推；loops=0 表示无限循环。"""
    import time as _t
    played = 0
    round_index = 0
    try:
        while True:
            for img, dur in zip(frames, durations):
                t0 = _t.perf_counter()
                panel.show(img)
                played += 1
                rest = max(0.0, dur - (_t.perf_counter() - t0))
                if rest:
                    _t.sleep(rest)
            round_index += 1
            if loops and round_index >= loops:
                break
    except KeyboardInterrupt:
        pass
    print("[usb] 共推 %d 帧（%d 轮）" % (played, round_index))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gif")
    ap.add_argument("--width", type=int, default=240)
    ap.add_argument("--height", type=int, default=240)
    ap.add_argument("--loops", type=int, default=0, help="0 = 无限循环")
    args = ap.parse_args()

    frames, durations = load_gif(args.gif, args.width, args.height)
    total = sum(durations)
    print("[info] %d 帧，单轮 %.2f 秒" % (len(frames), total))

    with ValkyriePanel(args.width, args.height) as panel:
        play(panel, frames, durations, args.loops)


if __name__ == "__main__":
    main()

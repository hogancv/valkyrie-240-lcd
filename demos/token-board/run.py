"""把 Token 看板推到屏上。

    python demos/token-board/run.py                    # 自动找数据，一直跑
    python demos/token-board/run.py --source sample    # 用内置演示数据
    python demos/token-board/run.py --seconds 30       # 跑 30 秒后退出
    python demos/token-board/run.py --once --save frame.png   # 只渲染不推流

刷新策略：数据不用每帧都读（SQLite 复制 + 聚合有毫秒级开销），
默认 15 秒重新取一次数，帧本身 2 fps 重推 —— 屏幕不会因为长期没写入而休眠或闪回 logo。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from PIL import Image  # noqa: E402

import data as datamod  # noqa: E402
from render import draw_board  # noqa: E402


def frames(interval: float, source: str):
    """惰性生成：每隔 interval 秒重新取一次数据，逐帧重绘。"""
    last = 0.0
    cached = None
    while True:
        now = time.monotonic()
        if cached is None or now - last >= interval:
            try:
                cached = datamod.load(source)
            except Exception as exc:                    # 数据层出错不能拖死屏幕
                print("[warn] 取数失败：%s" % exc, file=sys.stderr)
                cached = cached or datamod.sample()
            last = now
        yield draw_board(cached)


def main():
    ap = argparse.ArgumentParser(description="Token 看板：把用量数据推到 240x240 副屏")
    ap.add_argument("--source", choices=["auto", "token-monitor", "sample"], default="auto")
    ap.add_argument("--seconds", type=float, default=0, help="0 = 一直跑")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--refresh", type=float, default=15.0, help="多少秒重新取一次数")
    ap.add_argument("--once", action="store_true", help="只渲染一帧，不连设备")
    ap.add_argument("--save", default="", help="把渲染结果存成 png（可与 --once 搭配）")
    ap.add_argument("--preview", action="store_true", help="额外存一份 3 倍放大图")
    args = ap.parse_args()

    if args.once:
        img = draw_board(datamod.load(args.source))
        path = args.save or "frame.png"
        img.save(path)
        print("[save] %s" % path)
        if args.preview:
            img.resize((720, 720), Image.NEAREST).save(Path(path).with_name("frame@3x.png"))
        return

    from valkyrie_lcd import ValkyriePanel

    with ValkyriePanel(240, 240) as panel:
        try:
            panel.stream(frames(args.refresh, args.source), fps=args.fps,
                         seconds=args.seconds or None)
        except KeyboardInterrupt:
            print("\n[info] 已停止")


if __name__ == "__main__":
    main()

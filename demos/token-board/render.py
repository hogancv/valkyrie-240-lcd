"""Token 看板：把一段用量数据渲染成 240×240 的一帧。

这是作者本人在用的实现 —— 屏幕就挂在水冷头上，余光扫一眼就知道今天烧了多少。
它同时是「怎么用这个库做自己的东西」最完整的范例：数据层、画面层、调度层分得干干净净。

排版心得（1.5 寸屏、像素密度极高，10px 字肉眼基本不可读）：

  · 正文最小 12px，模型名 / token 数 15px，主数字 44px
  · 每个模型占两行：上行「名称 …… token 数」，下行「占比条 …… 费用」
  · 费用列宽度按两行的最大值预留，两条占比条右端才会对齐（不预留看着很脏）
  · 中英混排要用两个字体真实的 ascent 差做基线对齐，不能用同一个 y
  · 左右各留 12px 安全边距，任何文字都不进入边框 8px 内

这一层**纯渲染、不碰 USB** —— 在 Linux / macOS 上也能跑，方便调版式。

    python demos/token-board/render.py            # 生成 preview.png 直接看
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W = H = 240
PAD = 12

# ── 配色：深灰底 + 薄荷绿点缀，长时间看不刺眼 ──────────────────────────────
BG = (10, 10, 12)
FG = (242, 242, 246)
DIM = (150, 152, 162)
MID = (198, 200, 210)        # 次级数值：比 DIM 亮，物理屏上更易读
FAINT = (52, 52, 58)         # 分隔线
ACCENT = (110, 231, 183)     # 金额 / 在线点
BAR = (94, 234, 212)         # 占比条
TRACK = (30, 30, 36)         # 占比条底槽

# ── 字体：按优先级找第一个存在的，Windows / macOS / Linux 都能出图 ─────────
FONT_SETS = {
    "sans": [
        r"C:\Windows\Fonts\msyh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "sans_bold": [
        r"C:\Windows\Fonts\msyhbd.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "num": [
        r"C:\Windows\Fonts\bahnschrift.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}

_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    """取字体，带缓存（同一个 size 反复 truetype 会明显拖慢帧率）。"""
    key = (kind, size)
    if key in _cache:
        return _cache[key]
    for path in FONT_SETS.get(kind, []) + FONT_SETS["sans"]:
        try:
            f = ImageFont.truetype(path, size)
            _cache[key] = f
            return f
        except OSError:
            continue
    f = ImageFont.load_default()
    _cache[key] = f
    return f


def fmt_tokens(n: float) -> str:
    """155330000 -> '155.33M'，够短才放得进 44px 大字。

    末尾的 0 要削掉（'2.40K' -> '2.4K'），否则一排数字看着很啰嗦。
    """
    n = float(n or 0)
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return ("%.2f" % (n / div)).rstrip("0").rstrip(".") + unit
    return "%d" % n


def _fit(draw, text: str, fnt, max_w: float) -> str:
    """超宽就截断加省略号，绝不溢出边界。"""
    if draw.textlength(text, font=fnt) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=fnt) > max_w:
        text = text[:-1]
    return (text + "…") if text else ""


def draw_board(data: dict, width: int = W, height: int = H) -> Image.Image:
    """把 data 画成一帧。data 结构见 demos/token-board/README.md。

    today / month / all_time : {"tokens": int, "cost": float, "messages": int}
    top_models               : [{"name": str, "tokens": int, "cost": float}, ...]
    """
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    # ---- 字号档位 ----
    f_tag = font("sans_bold", 12)     # 顶部标签
    f_big = font("num", 44)           # 主数字
    f_cost = font("num", 20)          # 今日花费
    f_meta = font("sans", 13)         # 消息数
    f_sec = font("sans", 12)          # 分区标签
    f_val = font("num", 15)           # 模型 token 数
    f_mini = font("num", 13)          # 模型费用
    f_foot = font("num", 14)          # 页脚

    today = data.get("today") or {}
    month = data.get("month") or {}
    all_time = data.get("all_time") or {}

    # ---- 顶部：标签 + 实时在线点 ----
    d.text((PAD, 6), "TODAY", font=f_tag, fill=DIM)
    d.ellipse((width - PAD - 6, 11, width - PAD, 17), fill=ACCENT)

    # ---- 主数字：今日 token 总量 ----
    d.text((PAD - 2, 22), fmt_tokens(today.get("tokens", 0)), font=f_big, fill=FG)

    # ---- 花费（左）+ 消息数（右）----
    d.text((PAD - 1, 64), "$%.2f" % (today.get("cost") or 0), font=f_cost, fill=ACCENT)
    msg = "{:,} msgs".format(int(today.get("messages") or 0))
    d.text((width - PAD - d.textlength(msg, font=f_meta), 69), msg, font=f_meta, fill=DIM)

    # ---- 分隔线 ----
    d.line((PAD, 94, width - PAD, 94), fill=FAINT, width=1)

    # ---- 模型榜：今日 Top2，按 token 降序（只显示两个，字才够大）----
    d.text((PAD, 99), "TOP MODELS", font=f_sec, fill=DIM)
    models = (data.get("top_models") or [])[:2]
    peak = max((m["tokens"] for m in models), default=1) or 1
    # 费用列统一右对齐、宽度取两行最大值，两条占比条的右端才会对齐
    cw_max = max((d.textlength("$%.2f" % m["cost"], font=f_mini) for m in models), default=0)
    bar_max = width - PAD * 2 - cw_max - 8

    y = 118
    if not models:
        d.text((PAD, 132), "今日暂无模型用量", font=font("sans", 15), fill=DIM)
        d.text((PAD, 154), "等待客户端产生用量", font=f_meta, fill=(118, 120, 130))

    for m in models:
        name = m["name"]
        f_name = font("num" if name.isascii() else "sans", 15)
        val = fmt_tokens(m["tokens"])
        vw = d.textlength(val, font=f_val)                  # 按实际宽度预留
        label = _fit(d, name, f_name, width - PAD * 2 - vw - 12)
        d.text((PAD, y), label, font=f_name, fill=FG)
        # 用两个字体真实的 ascent 差做基线对齐，避免中英混排时错位
        dy = f_name.getmetrics()[0] - f_val.getmetrics()[0]
        d.text((width - PAD - vw, y + dy), val, font=f_val, fill=MID)

        # 下行：占比条在左、费用在右，压在同一条视觉线上
        cost_txt = "$%.2f" % m["cost"]
        cw = d.textlength(cost_txt, font=f_mini)
        bw = max(3, int(bar_max * m["tokens"] / peak))
        d.rectangle((PAD, y + 29, PAD + bw, y + 31), fill=BAR)
        d.rectangle((PAD + bw, y + 29, PAD + bar_max, y + 31), fill=TRACK)
        d.text((width - PAD - cw, y + 24), cost_txt, font=f_mini, fill=DIM)
        y += 40

    # ---- 页脚：累计 / 本月 ----
    d.line((PAD, 200, width - PAD, 200), fill=FAINT, width=1)
    left = "ALL " + fmt_tokens(all_time.get("tokens", 0))
    right = "MO " + fmt_tokens(month.get("tokens", 0))
    d.text((PAD, 207), left, font=f_foot, fill=DIM)
    d.text((width - PAD - d.textlength(right, font=f_foot), 207), right,
           font=f_foot, fill=DIM)
    return img


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import data as datamod

    img = draw_board(datamod.load())
    out = Path(__file__).resolve().parent / "preview.png"
    img.save(out)
    img.resize((W * 3, H * 3), Image.NEAREST).save(out.with_name("preview@3x.png"))
    print("[save] %s" % out)
    print("[save] %s" % out.with_name("preview@3x.png"))


if __name__ == "__main__":
    main()

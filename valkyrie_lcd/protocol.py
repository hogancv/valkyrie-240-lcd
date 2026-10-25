"""协议真值：VIC 表、HID 命令序列、帧结构。

这些数值不是猜的，全部来自官方驱动自己的日志
(`%APPDATA%\\WinUsbDisplay\\winusbdisplay *.log`)，并与开源实现交叉验证过。
改动任何一个字节前，先读 docs/PROTOCOL.md 的理由说明。
"""

from __future__ import annotations

# ── 设备指纹 ────────────────────────────────────────────────────────────────
VID = 0x345F
PID = 0x9132
INTERFACE_HID = 0      # MI_00：HID 特征报文（EP0 控制传输）
INTERFACE_BULK = 3     # MI_03：像素流 bulk OUT
EP_OUT = 0x04

# ── 帧结构 ──────────────────────────────────────────────────────────────────
FRAME_HEADER_LEN = 8
FRAME_FOOTER_LEN = 8
FRAME_FOOTER = bytes([0xFF, 0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

# 每推 COMMIT_EVERY 帧补一条 B5 00 32（官方软件约 38 帧一次，取 30 足够稳）
COMMIT_EVERY = 30

# ── 像素格式码（A6 01 的第 7 字节）─────────────────────────────────────────
# 对应 MacroSilicon ms912x 驱动的 MS912X_PIXFMT_* 常量：
#   0x11 → RGB888，3 字节/像素
#   0x22 → YUV422(UYVY)，2 字节/像素
# 本仓库固定走 0x22。发 0x11 会让固件按 720 字节/行解析（240 像素 × 3），
# 于是画面横向重复 3 次、纵向只填满 160 行 —— 这是最经典的一个坑。
PIXFMT_YUV422 = 0x22
PIXFMT_RGB888 = 0x11

# ── VIC（视频模式码）表 ─────────────────────────────────────────────────────
# 取自官方 MSDisplayAddon 日志里的 "MSDevice Config" 静态表。
# vic   : 面板固件认的模式编号，写进 A6 02 命令
# size  : (hactive, vactive) 物理像素
# 其余  : 该模式的时序参数，仅作记录/校验用，实际由固件按 VIC 自行展开
VIC_TABLE = {
    143: dict(size=(480, 480), htotal=600,  vtotal=490,  pixclk=1764,
              hoff=100, voff=8,   hsync=50, vsync=4),
    147: dict(size=(240, 320), htotal=452,  vtotal=568,  pixclk=1540,
              hoff=190, voff=260, hsync=5,  vsync=20),
    148: dict(size=(320, 240), htotal=568,  vtotal=452,  pixclk=1540,
              hoff=206, voff=190, hsync=20, vsync=5),
    156: dict(size=(240, 240), htotal=640,  vtotal=352,  pixclk=1350,
              hoff=190, voff=51,  hsync=10, vsync=10),
    159: dict(size=(480, 272), htotal=600,  vtotal=375,  pixclk=1350,
              hoff=100, voff=90,  hsync=50, vsync=5),
    160: dict(size=(360, 960), htotal=544,  vtotal=996,  pixclk=3263,
              hoff=102, voff=33,  hsync=40, vsync=10),
}


def vic_for(width: int, height: int):
    """按物理分辨率反查 VIC；不在表里返回 None。"""
    for vic, spec in VIC_TABLE.items():
        if spec["size"] == (width, height):
            return vic
    return None


def frame_header(width: int, height: int) -> bytes:
    """8 字节帧头：FF 00 | x/16 | y(BE16) | width/16 | height(BE16)。

    240×240 全屏刷新 → FF 00 00 00 00 0F 00 F0
      x=0（/16 后仍为 0）、y=0、width=240/16=15=0x0F、height=240=0x00F0
    注意 height 是「像素数」不是「/16」，这一处很多实现都写错了。
    """
    return bytes([
        0xFF, 0x00,
        0x00,                                   # x / 16
        0x00, 0x00,                             # y (BE16)
        (width // 16) & 0xFF,                   # width / 16
        (height >> 8) & 0xFF, height & 0xFF,    # height (BE16，像素数)
    ])


def frame_size(width: int, height: int) -> int:
    """整帧字节数 = 头 8 + 像素 + 尾 8。240×240 为 115216。"""
    return FRAME_HEADER_LEN + width * height * 2 + FRAME_FOOTER_LEN


def pack_cmd(*heads) -> bytes:
    """把一条命令补成 8 字节。"""
    out = bytearray(8)
    out[: min(len(heads), 8)] = bytes(heads[:8])
    return bytes(out)


def build_init_sequence(width: int, height: int, vic: int | None = None,
                        mode: int = PIXFMT_YUV422,
                        geom_a601: bytes | None = None,
                        geom_a602: bytes | None = None):
    """完整冷启动序列，返回 [(payload8, 是否需要读回), ...]。

    共 76 条（含两条携带几何参数的 A6 命令）。缺了其中任何一段，
    面板要么保持黑屏，要么显示但画面错位 —— 这不是"可选的初始化"。
    序列结构移植自 LcdFusion(MIT) 的 ValkyrieHidInitializer，
    参数部分按本机官方日志校正。
    """
    seq = []

    def cmd(need_read, *heads):
        seq.append((pack_cmd(*heads), need_read))

    # --- 传输模式 / 屏幕闸门 ---------------------------------------------
    cmd(False, 0xA6, 0x03, 0x03)
    cmd(True,  0xB5, 0xC5, 0x58)
    cmd(False, 0xB6, 0xDE, 0xEE, 0x01)
    cmd(False, 0xA6, 0x07, 0x01, 0x02)
    cmd(True,  0xB5, 0xC4, 0x54)
    cmd(False, 0xA6, 0x05, 0x00)
    cmd(True,  0xB5, 0xC5, 0x55)
    cmd(True,  0xB5, 0xF0, 0x04)
    cmd(False, 0xB6, 0xF0, 0x04, 0x6D)     # 官方日志：addr 0xf004 ← 0x6D

    # --- 面板控制器寄存器 / gamma 表（缺这段面板一直黑）------------------
    for addr in (0xE0, 0xE8, 0xF0, 0xF8):
        cmd(True, 0xF5, 0x00, 0x1F, addr)
    cmd(True, 0xB5, 0xC4, 0x24)
    cmd(True, 0xB5, 0xC6, 0x50)
    cmd(True, 0xB5, 0xC3, 0x0F)
    cmd(True, 0xB5, 0xFF, 0x00)
    cmd(True, 0xB5, 0xF0, 0x00)
    cmd(True, 0xB5, 0x00, 0x31)
    cmd(True, 0xB5, 0x00, 0x30)
    cmd(True, 0xB5, 0x00, 0x32)
    cmd(True, 0xB5, 0x00, 0x32)
    for value in range(0x00, 0x7D, 0x04):   # gamma 斜坡
        cmd(True, 0xB5, 0xC0, value)
    for addr in (0xE0, 0xE8, 0xF0, 0xF8):
        cmd(True, 0xF5, 0x00, 0x1F, addr)
    cmd(True, 0xB5, 0x00, 0x32)

    # --- 几何 / 使能：A6 01 定像素格式，A6 02 定 VIC ----------------------
    cmd(False, 0xA6, 0x05, 0x00)
    cmd(True,  0xB5, 0xC5, 0x55)
    cmd(True,  0xB5, 0xF5, 0x07)
    cmd(False, 0xB6, 0xF5, 0x07, 0x02)     # 官方日志：addr 0xf507 ← 0x02（mem freeze）
    cmd(False, 0xA6, 0x04, 0x00)
    cmd(True,  0xB5, 0xC5, 0x55)
    cmd(True,  0xB5, 0x00, 0x32)
    cmd(False, 0xA6, 0x03, 0x03)
    cmd(True,  0xB5, 0xC5, 0x58)

    if geom_a601 is None:
        geom_a601 = bytes([0xA6, 0x01,
                           (width >> 8) & 0xFF, width & 0xFF,
                           (height >> 8) & 0xFF, height & 0xFF,
                           mode, 0x00])
    seq.append((bytes(geom_a601[:8]), False))
    cmd(True, 0xB5, 0xC5, 0x55)

    if geom_a602 is None:
        if vic is None:
            vic = vic_for(width, height)
        if vic is None:
            raise ValueError(
                "%dx%d 不在 VIC 表里（可选：%s）" % (
                    width, height,
                    ", ".join("%dx%d" % v["size"] for v in VIC_TABLE.values())))
        geom_a602 = bytes([0xA6, 0x02, vic, 0x00,
                           (width >> 8) & 0xFF, width & 0xFF,
                           (height >> 8) & 0xFF, height & 0xFF])
    seq.append((bytes(geom_a602[:8]), True))

    # --- 收尾：解除 mem freeze，打开视频输出 ------------------------------
    cmd(False, 0xA6, 0x04, 0x01, 0x00)
    cmd(True,  0xB5, 0xC5, 0x55)
    cmd(False, 0xB6, 0xF2, 0x4E, 0x00)
    cmd(True,  0xB5, 0x00, 0x32)
    cmd(True,  0xB5, 0xF2, 0x42, 0x00)
    return seq


# 首帧之后必须补这一组，否则面板停在 mem freeze 状态，画面不刷新
POST_FRAME_SEQUENCE = (
    (pack_cmd(0xB5, 0xF5, 0x07), True),
    (pack_cmd(0xB6, 0xF5, 0x07, 0x00), False),
    (pack_cmd(0xA6, 0x05, 0x01, 0x00), False),
    (pack_cmd(0xB5, 0xC5, 0x55), True),
)

# 帧间保活
COMMIT_CMD = pack_cmd(0xB5, 0x00, 0x32)


def describe(width: int, height: int) -> str:
    """返回一句话自检摘要，便于打日志。"""
    vic = vic_for(width, height)
    return ("%dx%d  VIC=%s  fmt=0x%02X  帧长=%d 字节  帧头=%s"
            % (width, height, vic, PIXFMT_YUV422,
               frame_size(width, height), frame_header(width, height).hex(" ")))

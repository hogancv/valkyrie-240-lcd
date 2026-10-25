"""RGB → UYVY(YUV 4:2:2) 转换。

固件要的是 2 字节/像素的 UYVY，字节序为 U Y0 V Y1。
用 BT.601 的 studio swing（Y 16–235 / UV 128±112），与官方软件一致；
用全范围 0–255 也能出图，但黑会不够黑、白会发灰。

依赖 numpy 做向量运算 —— 纯 Python 循环在 240×240@10fps 下会掉帧。
"""

from __future__ import annotations

import numpy as np


def to_uyvy(image, width: int, height: int) -> bytes:
    """PIL.Image → UYVY 字节流（长度 = width * height * 2）。

    水平方向每两个像素共享一组 U/V（取两者均值）。
    宽度必须是偶数，YUV 4:2:2 的硬性要求。
    """
    if width % 2:
        raise ValueError("宽度必须为偶数，当前 %d" % width)

    rgb = np.asarray(image.convert("RGB").resize((width, height)), dtype=np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    y = 0.257 * r + 0.504 * g + 0.098 * b + 16.0
    u = -0.148 * r - 0.291 * g + 0.439 * b + 128.0
    v = 0.439 * r - 0.368 * g - 0.071 * b + 128.0

    y = np.clip(y, 0, 255).astype(np.uint8)
    u = np.clip(u, 0, 255).astype(np.uint16)
    v = np.clip(v, 0, 255).astype(np.uint16)

    u2 = ((u[:, 0::2] + u[:, 1::2]) >> 1).astype(np.uint8)
    v2 = ((v[:, 0::2] + v[:, 1::2]) >> 1).astype(np.uint8)

    out = np.empty((height, width // 2, 4), dtype=np.uint8)
    out[..., 0] = u2
    out[..., 1] = y[:, 0::2]
    out[..., 2] = v2
    out[..., 3] = y[:, 1::2]
    return out.tobytes()

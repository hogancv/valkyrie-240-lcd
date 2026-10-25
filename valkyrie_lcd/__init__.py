"""valkyrie_lcd — 瓦尔基里 / Myth.Cool 水冷副屏（MacroSilicon MS9132）推流库。

    from valkyrie_lcd import ValkyriePanel
    from PIL import Image

    with ValkyriePanel() as panel:
        panel.show(Image.open("photo.jpg"))

协议层真值见 docs/PROTOCOL.md，踩坑记录见 docs/PITFALLS.md。
"""

from .panel import PanelError, ValkyriePanel
from .protocol import (
    COMMIT_EVERY, EP_OUT, FRAME_FOOTER, PIXFMT_RGB888, PIXFMT_YUV422, PID, VID,
    VIC_TABLE, build_init_sequence, describe, frame_header, frame_size, vic_for,
)

__version__ = "1.0.0"

__all__ = [
    "ValkyriePanel", "PanelError",
    "VID", "PID", "EP_OUT", "VIC_TABLE", "vic_for", "describe",
    "frame_header", "frame_size", "FRAME_FOOTER",
    "PIXFMT_YUV422", "PIXFMT_RGB888", "COMMIT_EVERY", "build_init_sequence",
]

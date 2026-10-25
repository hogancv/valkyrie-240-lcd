"""推流主类：一条 USB 线上的两段通道 + 帧拼装。

典型用法：

    from PIL import Image
    from valkyrie_lcd import ValkyriePanel

    with ValkyriePanel() as panel:          # 240×240，自动挑 VIC
        panel.show(Image.open("photo.jpg"))

长这样就行 —— `with` 里已经跑完 76 条初始化命令、打开了 bulk 端点。
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path

from .color import to_uyvy
from .hid import HidDevice
from .protocol import (
    COMMIT_CMD, COMMIT_EVERY, EP_OUT, FRAME_FOOTER, INTERFACE_BULK,
    PIXFMT_YUV422, POST_FRAME_SEQUENCE, build_init_sequence, describe,
    frame_header, frame_size, vic_for,
)

try:
    import usb.core
    from usb.backend import libusb0
except ImportError:                                  # pragma: no cover
    usb = None


class PanelError(RuntimeError):
    pass


class ValkyriePanel:
    """一块 MacroSilicon MS9132 屏（VID 345F / PID 9132）。

    参数
      width/height : 物理像素。240×240 是 VIC 156，其余见 protocol.VIC_TABLE。
      vic          : 一般不用管，按尺寸自动查表；查不到必须显式给。
      mode         : 像素格式码，默认 0x22(UYVY)。改成 0x11 会花屏。
      verbose      : 是否打印初始化细节。
    """

    def __init__(self, width: int = 240, height: int = 240,
                 vic: int | None = None, mode: int = PIXFMT_YUV422,
                 verbose: bool = True,
                 geom_a601: bytes | None = None,
                 geom_a602: bytes | None = None):
        self.width, self.height = width, height
        self.verbose = verbose
        self.mode = mode
        self.vic = vic if vic is not None else vic_for(width, height)
        if self.vic is None:
            raise PanelError(
                "%dx%d 不在 VIC 表里，请显式指定 vic=（24 位可选项见 protocol.VIC_TABLE）"
                % (width, height))
        self.geom_a601 = geom_a601
        self.geom_a602 = geom_a602

        self.header = frame_header(width, height)
        self.frame_len = frame_size(width, height)
        self.hid: HidDevice | None = None
        self.dev = None
        self.frame_index = 0
        self._first_frame_done = False
        self._last_image = None

    # ── 连接 ────────────────────────────────────────────────────────────────
    def connect(self) -> "ValkyriePanel":
        if self.verbose:
            print("[cfg] " + describe(self.width, self.height))
        self.open_hid()
        self.run_init()
        self.open_bulk()
        return self

    def open_hid(self) -> "ValkyriePanel":
        self.hid = HidDevice().open()
        if self.verbose:
            print("[hid] %s  feature_report=%d 字节" % (self.hid.path, self.hid.feature_len))
        return self

    def run_init(self) -> int:
        """下发 76 条冷启动命令。返回失败条数（0 为理想）。"""
        seq = build_init_sequence(self.width, self.height, vic=self.vic,
                                  mode=self.mode, geom_a601=self.geom_a601,
                                  geom_a602=self.geom_a602)
        errors = 0
        for payload, need_read in seq:
            try:
                self.hid.set_feature(payload)
                if need_read:
                    try:
                        self.hid.get_feature()
                    except OSError:
                        pass
            except OSError as exc:
                errors += 1
                if self.verbose and errors <= 3:
                    print("[hid] 命令 %s 失败: %s" % (payload[:3].hex(" "), exc))
        if self.verbose:
            print("[hid] 初始化完成：%d 条，失败 %d" % (len(seq), errors))
        return errors

    def open_bulk(self) -> "ValkyriePanel":
        if usb is None:
            raise PanelError("未安装 pyusb：pip install pyusb")
        self.dev = usb.core.find(idVendor=0x345F, idProduct=0x9132,
                                 backend=libusb0.get_backend())
        if self.dev is None:
            raise PanelError(
                "找不到 bulk 设备。常见原因：\n"
                "  1) 官方软件还开着，占着设备\n"
                "  2) MI_03 没绑 libusb-win32（设备管理器里应为 libusb-win32 devices）")
        for fn in ("set_configuration", "clear_halt"):
            try:
                if fn == "clear_halt":
                    self.dev.clear_halt(EP_OUT)
                else:
                    self.dev.set_configuration()
            except Exception:
                pass
        try:
            self.dev.set_interface_altsetting(interface=INTERFACE_BULK,
                                              alternate_setting=0)
        except Exception:
            pass
        if self.verbose:
            print("[usb] bulk 已就绪 addr=%s  ep=0x%02X" % (self.dev.address, EP_OUT))
        return self

    def close(self):
        """释放句柄。

        绝不调用 dev.reset()：MS9132 收到 USB 总线复位会固件挂死，
        表现为设备变成 VID_0000&PID_0005「设备描述符错误」，
        拔插/断电都救不回来，只能用 pnputil 重启父级集线器。
        """
        if self.dev is not None:
            for fn in ("finalize", "_finalize"):
                try:
                    getattr(self.dev, fn)()
                    break
                except Exception:
                    continue
            self.dev = None
        if self.hid is not None:
            self.hid.close()
            self.hid = None

    # ── 帧 ──────────────────────────────────────────────────────────────────
    def build_frame(self, image) -> bytes:
        return self.header + to_uyvy(image, self.width, self.height) + FRAME_FOOTER

    def write_frame(self, frame: bytes, timeout: int = 2000) -> int:
        written = self.dev.write(EP_OUT, frame, timeout)
        if written != len(frame):
            raise IOError("短写 %d/%d 字节" % (written, len(frame)))
        return written

    def _post_frame(self):
        for payload, need_read in POST_FRAME_SEQUENCE:
            try:
                self.hid.set_feature(payload)
                if need_read:
                    self.hid.get_feature()
            except OSError:
                pass

    def _commit(self):
        try:
            self.hid.set_feature(COMMIT_CMD)
            self.hid.get_feature()
        except OSError:
            pass

    def show(self, image, timeout: int = 2000) -> float:
        """推一帧，返回耗时（秒）。首帧会自动补 post-frame 序列。"""
        t0 = time.perf_counter()
        self._last_image = image
        self.write_frame(self.build_frame(image), timeout=timeout)
        if not self._first_frame_done:
            self._post_frame()
            self._first_frame_done = True
        elif self.frame_index % COMMIT_EVERY == 0:
            self._commit()
        self.frame_index += 1
        return time.perf_counter() - t0

    def stream(self, frames, fps: float = 8.0, seconds: float | None = None,
               loop: bool = True):
        """连续推流。

        frames  可迭代的 PIL.Image（列表会循环使用；生成器则惰性取帧，
                适合「时钟」「实时数据」这类永远画不完的内容）
        fps     目标帧率；实测 240×240 单帧约 22 ms，10 fps 很轻松
        seconds 推多久；None 表示无限（配合 Ctrl+C）
        loop    列表帧用完后是否重头再来
        """
        if isinstance(frames, Sequence) and not isinstance(frames, (str, bytes)):
            if not frames:
                raise PanelError("没有可推的帧")
            seq = list(frames)

            def cycle():
                i = 0
                while True:
                    yield seq[i % len(seq)]
                    i += 1
                    if not loop and i >= len(seq):
                        return
            iterator = cycle()
        else:
            iterator = iter(frames)          # 惰性：生成器可以是无限的

        interval = 1.0 / max(fps, 0.1)
        deadline = None if seconds is None else time.perf_counter() + seconds
        pushed = 0
        try:
            for image in iterator:
                if deadline is not None and time.perf_counter() >= deadline:
                    break
                t0 = time.perf_counter()
                self.show(image, timeout=2000)
                pushed += 1
                rest = interval - (time.perf_counter() - t0)
                if rest > 0:
                    time.sleep(rest)
        finally:
            if self.verbose:
                print("[usb] 已推 %d 帧" % pushed)
        return pushed

    def hold(self, seconds: float = 5.0, fps: float = 2.0):
        """保持最后一帧不闪：低速重推同一画面。"""
        last = getattr(self, "_last_image", None)
        if last is None:
            return
        self.stream([last], fps=fps, seconds=seconds)

    # ── 便利方法 ────────────────────────────────────────────────────────────
    def show_file(self, path: str | Path):
        from PIL import Image
        img = Image.open(path).convert("RGB")
        self._last_image = img
        return self.show(img)

    # ── 上下文管理 ──────────────────────────────────────────────────────────
    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

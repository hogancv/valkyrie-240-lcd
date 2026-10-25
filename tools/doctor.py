"""环境自检：跑不起来时先跑这个。

    python tools/doctor.py

它只读不写，不会碰设备状态。
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VID, PID = 0x345F, 0x9132
OK, WARN, BAD = "[ OK ]", "[WARN]", "[FAIL]"


def line(tag, msg):
    print("%s %s" % (tag, msg))


def check_python():
    v = sys.version_info
    if v >= (3, 10):
        line(OK, "Python %d.%d.%d" % (v[0], v[1], v[2]))
    else:
        line(WARN, "Python %d.%d.%d（建议 3.10+）" % (v[0], v[1], v[2]))
    if platform.system() != "Windows":
        line(BAD, "HID 通道依赖 Windows hid.dll，本库仅支持 Windows")
        return False
    line(OK, "Windows %s" % platform.release())
    return True


def check_deps():
    ok = True
    try:
        import numpy
        line(OK, "numpy %s" % numpy.__version__)
    except ImportError:
        line(BAD, "缺 numpy → pip install numpy")
        ok = False
    try:
        import PIL
        line(OK, "Pillow %s" % PIL.__version__)
    except ImportError:
        line(BAD, "缺 Pillow → pip install pillow")
        ok = False
    try:
        import usb
        line(OK, "pyusb %s" % getattr(usb, "__version__", "?"))
    except ImportError:
        line(BAD, "缺 pyusb → pip install pyusb")
        ok = False
    try:
        import psutil
        line(OK, "psutil %s（可选）" % psutil.__version__)
    except ImportError:
        line(WARN, "无 psutil（可选，仅影响示例 04 的 CPU/内存显示）")
    return ok


def check_backend():
    """libusb0 后端能否加载 —— 这是 MI_03 能不能通的前提。"""
    try:
        from usb.backend import libusb0
    except ImportError:
        line(BAD, "pyusb 未安装")
        return False
    backend = libusb0.get_backend()
    if backend is None:
        line(BAD, "libusb0 后端加载失败：找不到 libusb0.dll")
        line(WARN, "  MI_03 需要绑定 libusb-win32 驱动（Zadig 或官方软件安装时自带）")
        return False
    line(OK, "libusb0 后端已加载")
    return True


def check_device():
    try:
        import usb.core
        from usb.backend import libusb0
    except ImportError:
        return
    dev = usb.core.find(idVendor=VID, idProduct=PID, backend=libusb0.get_backend())
    if dev is None:
        line(BAD, "找不到 VID=%04X PID=%04X" % (VID, PID))
        line(WARN, "  排查：① 线/接口 ② 官方软件是否已卸载 ③ MI_03 是否绑 libusb-win32")
        line(WARN, "  若设备管理器里出现「设备描述符错误」(VID_0000&PID_0005)，"
                   "见 docs/PITFALLS.md 的恢复步骤")
        return
    speed = getattr(dev, "speed", None)
    line(OK, "设备已枚举：bus=%s addr=%s%s"
         % (dev.bus, dev.address, ("  速度=%s Mbps" % speed) if speed else ""))


def check_hid():
    try:
        from valkyrie_lcd.hid import HidDevice
    except Exception as exc:
        line(BAD, "无法导入 valkyrie_lcd.hid: %s" % exc)
        return
    try:
        hid = HidDevice(VID, PID).open()
        line(OK, "HID 控制接口可打开（feature_report=%d 字节）" % hid.feature_len)
        hid.close()
    except Exception as exc:
        line(BAD, "HID 接口打不开：%s" % exc)
        line(WARN, "  通常是官方 Myth.Cool 软件还开着，占用了 MI_00")


def main():
    print("=" * 62)
    print("valkyrie_lcd 环境自检")
    print("=" * 62)
    print("\n-- 系统 --")
    check_python()
    print("\n-- 依赖 --")
    deps = check_deps()
    print("\n-- 驱动后端 --")
    backend_ok = check_backend()
    print("\n-- 设备 --")
    if deps and backend_ok:
        check_device()
        check_hid()
    else:
        line(WARN, "依赖不全，跳过设备检查")
    print("\n-- 结论 --")
    if deps and backend_ok:
        print("基础环境就绪。接着跑：python examples/01_testcard.py")
    else:
        print("先补齐上面标 FAIL 的项再试。")


if __name__ == "__main__":
    main()

"""HID 特征报文通道（Windows hid.dll，ctypes 直调，无第三方依赖）。

面板的控制通道走 MI_00（标准 HID 接口），每条命令是一个 9 字节特征报文：
第 0 字节是 report id（恒为 0），后面 8 字节是负载。

**只有在 Windows 上真正调用 open() 时才会去加载 hid.dll。**
也就是说这个模块可以被任何平台 import —— 方便在 Linux/CI 上跑协议层单元测试，
`import valkyrie_lcd` 不会因为缺 Windows DLL 而炸。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys

from .protocol import PID, VID

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x1
FILE_SHARE_WRITE = 0x2
OPEN_EXISTING = 3
DIGCF_PRESENT = 0x2
DIGCF_DEVICEINTERFACE = 0x10
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD),
                ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


_GUID_DEVINTERFACE_HID = _GUID(0x4D1E55B2, 0xF16F, 0x11CF,
                              (0x88, 0xCB, 0x00, 0x11, 0x11, 0x00, 0x00, 0x30))


class _SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("InterfaceClassGuid", _GUID),
                ("Flags", wt.DWORD), ("Reserved", ctypes.c_void_p)]


class _HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wt.ULONG), ("VendorID", wt.USHORT),
                ("ProductID", wt.USHORT), ("VersionNumber", wt.USHORT)]


class _HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
        ("InputReportByteLength", wt.USHORT),
        ("OutputReportByteLength", wt.USHORT),
        ("FeatureReportByteLength", wt.USHORT),
        ("Reserved", wt.USHORT * 17),
        ("NumberLinkCollectionNodes", wt.USHORT),
        ("NumberInputButtonCaps", wt.USHORT),
        ("NumberInputValueCaps", wt.USHORT),
        ("NumberInputDataIndices", wt.USHORT),
        ("NumberOutputButtonCaps", wt.USHORT),
        ("NumberOutputValueCaps", wt.USHORT),
        ("NumberOutputDataIndices", wt.USHORT),
        ("NumberFeatureButtonCaps", wt.USHORT),
        ("NumberFeatureValueCaps", wt.USHORT),
        ("NumberFeatureDataIndices", wt.USHORT),
    ]


class _Libs:
    """延迟加载的 Win32 函数表（只在 Windows 上 open() 时才构造）。"""

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("本库的 HID 通道依赖 Windows hid.dll，当前平台：%s"
                               % sys.platform)
        self.hid = ctypes.WinDLL("hid.dll")
        self.setupapi = ctypes.WinDLL("setupapi.dll")
        self.kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
        self._prototype()

    def _prototype(self):
        api, hid, k32 = self.setupapi, self.hid, self.kernel32

        api.SetupDiGetClassDevsW.restype = ctypes.c_void_p
        api.SetupDiGetClassDevsW.argtypes = [
            ctypes.POINTER(_GUID), ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
        api.SetupDiEnumDeviceInterfaces.restype = wt.BOOL
        api.SetupDiEnumDeviceInterfaces.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_GUID), wt.DWORD,
            ctypes.POINTER(_SP_DEVICE_INTERFACE_DATA)]
        api.SetupDiGetDeviceInterfaceDetailW.restype = wt.BOOL
        api.SetupDiGetDeviceInterfaceDetailW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(_SP_DEVICE_INTERFACE_DATA),
            ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
        api.SetupDiDestroyDeviceInfoList.restype = wt.BOOL
        api.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

        k32.CreateFileW.restype = ctypes.c_void_p
        k32.CreateFileW.argtypes = [
            wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD,
            ctypes.c_void_p]
        k32.CloseHandle.restype = wt.BOOL
        k32.CloseHandle.argtypes = [ctypes.c_void_p]

        hid.HidD_GetAttributes.restype = wt.BOOL
        hid.HidD_GetAttributes.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(_HIDD_ATTRIBUTES)]
        hid.HidD_SetFeature.restype = wt.BOOL
        hid.HidD_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
        hid.HidD_GetFeature.restype = wt.BOOL
        hid.HidD_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
        hid.HidD_GetPreparsedData.restype = wt.BOOL
        hid.HidD_GetPreparsedData.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        hid.HidD_FreePreparsedData.restype = wt.BOOL
        hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
        hid.HidP_GetCaps.restype = wt.LONG
        hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(_HIDP_CAPS)]


_LIBS: _Libs | None = None


def _libs() -> _Libs:
    global _LIBS
    if _LIBS is None:
        _LIBS = _Libs()
    return _LIBS


def iter_hid_paths():
    """枚举系统里所有 HID 设备接口路径。"""
    libs = _libs()
    api = libs.setupapi
    guid = _GUID_DEVINTERFACE_HID
    info_set = api.SetupDiGetClassDevsW(
        ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if info_set == INVALID_HANDLE_VALUE or info_set in (None, 0):
        return
    try:
        index = 0
        while True:
            did = _SP_DEVICE_INTERFACE_DATA()
            did.cbSize = ctypes.sizeof(_SP_DEVICE_INTERFACE_DATA)
            if not api.SetupDiEnumDeviceInterfaces(
                    info_set, None, ctypes.byref(guid), index, ctypes.byref(did)):
                break
            index += 1
            required = wt.DWORD(0)
            api.SetupDiGetDeviceInterfaceDetailW(
                info_set, ctypes.byref(did), None, 0, ctypes.byref(required), None)
            if not required.value:
                continue
            buf = ctypes.create_string_buffer(required.value)
            cb = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            ctypes.memmove(buf, ctypes.byref(wt.DWORD(cb)), 4)
            if not api.SetupDiGetDeviceInterfaceDetailW(
                    info_set, ctypes.byref(did), buf, required.value,
                    ctypes.byref(required), None):
                continue
            yield ctypes.wstring_at(ctypes.addressof(buf) + 4)
    finally:
        api.SetupDiDestroyDeviceInfoList(info_set)


class HidDevice:
    """屏幕的 HID 控制句柄（MI_00）。"""

    def __init__(self, vid: int = VID, pid: int = PID):
        self.vid, self.pid = vid, pid
        self.handle = None
        self.path = None
        self.feature_len = 9

    def open(self) -> "HidDevice":
        libs = _libs()
        for path in iter_hid_paths():
            handle = libs.kernel32.CreateFileW(
                path, GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
            if not handle or handle == INVALID_HANDLE_VALUE:
                continue
            attrs = _HIDD_ATTRIBUTES()
            attrs.Size = ctypes.sizeof(_HIDD_ATTRIBUTES)
            if (libs.hid.HidD_GetAttributes(ctypes.c_void_p(handle), ctypes.byref(attrs))
                    and attrs.VendorID == self.vid and attrs.ProductID == self.pid):
                self.handle = ctypes.c_void_p(handle)
                self.path = path
                self._read_caps()
                return self
            libs.kernel32.CloseHandle(ctypes.c_void_p(handle))
        raise RuntimeError(
            "找不到 HID 接口 (VID=%04X PID=%04X)。检查设备是否插好、"
            "以及 MI_00 是否被占用（官方软件开着会抢）。" % (self.vid, self.pid))

    def _read_caps(self):
        libs = _libs()
        preparsed = ctypes.c_void_p()
        if not libs.hid.HidD_GetPreparsedData(self.handle, ctypes.byref(preparsed)):
            return
        if not preparsed:
            return
        try:
            caps = _HIDP_CAPS()
            if libs.hid.HidP_GetCaps(preparsed, ctypes.byref(caps)) >= 0:
                if caps.FeatureReportByteLength:
                    self.feature_len = caps.FeatureReportByteLength
        finally:
            libs.hid.HidD_FreePreparsedData(preparsed)

    def set_feature(self, payload8: bytes):
        libs = _libs()
        size = max(self.feature_len, 9)
        buf = ctypes.create_string_buffer(size)
        ctypes.memmove(buf, bytes([0x00]) + bytes(payload8[:8]), 9)
        if not libs.hid.HidD_SetFeature(self.handle, buf, size):
            raise OSError(ctypes.get_last_error(),
                          "HidD_SetFeature %s" % bytes(payload8[:3]).hex(" "))

    def get_feature(self, size: int | None = None) -> bytes:
        libs = _libs()
        size = size or max(self.feature_len, 9)
        buf = ctypes.create_string_buffer(size)
        if not libs.hid.HidD_GetFeature(self.handle, buf, size):
            raise OSError(ctypes.get_last_error(), "HidD_GetFeature")
        return bytes(buf.raw[:size])

    def close(self):
        if self.handle:
            _libs().kernel32.CloseHandle(self.handle)
            self.handle = None

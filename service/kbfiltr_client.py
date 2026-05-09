"""
kbfiltr_client.py — Python ctypes client for kbfiltr.sys.

Opens \\.\SynaplessFilter, sends the macro scan-code list via IOCTL, and
yields key events from a blocking ReadFile loop.

Usage:
    client = KbfiltrClient()
    if not client.open():
        ...  # driver not loaded — fall back to hook approach
    client.set_macro_keys({"1", "q", "e"})
    for name, is_keyup in client.read_events():
        ...
    client.close()
"""

import ctypes
import ctypes.wintypes
import logging
from typing import Generator, Optional, Tuple

log = logging.getLogger(__name__)

# ── Win32 constants ───────────────────────────────────────────────────────────

GENERIC_READ    = 0x80000000
GENERIC_WRITE   = 0x40000000
FILE_SHARE_READ  = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING   = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080

_INVALID_HANDLE = ctypes.wintypes.HANDLE(-1).value

# ── IOCTL ─────────────────────────────────────────────────────────────────────

# CTL_CODE(DeviceType=0x8031, Function=0x801, Method=0, Access=0x0002)
# = (0x8031 << 16) | (0x0002 << 14) | (0x801 << 2) | 0 = 0x8031A004
IOCTL_SYNAPLESS_SET_MACRO_KEYS = 0x8031A004

SYNAPLESS_MAX_MACRO_KEYS = 64

# ── Key event struct (mirrors kbfiltr.h SYNAPLESS_KEY_EVENT) ─────────────────

KEY_MAKE  = 0x00
KEY_BREAK = 0x01
KEY_E0    = 0x02
KEY_E1    = 0x04


class _KeyEvent(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('MakeCode', ctypes.c_ushort),
        ('Flags',    ctypes.c_ushort),
    ]


# ── Win32 API ─────────────────────────────────────────────────────────────────

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)

_k32.CreateFileW.restype  = ctypes.wintypes.HANDLE
_k32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HANDLE,
]

_k32.CloseHandle.restype  = ctypes.wintypes.BOOL
_k32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

_k32.DeviceIoControl.restype  = ctypes.wintypes.BOOL
_k32.DeviceIoControl.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.wintypes.DWORD),
    ctypes.c_void_p,
]

_k32.ReadFile.restype  = ctypes.wintypes.BOOL
_k32.ReadFile.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.wintypes.DWORD),
    ctypes.c_void_p,
]

_u32 = ctypes.WinDLL('user32', use_last_error=True)
_u32.MapVirtualKeyW.restype  = ctypes.c_uint
_u32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]

_MAPVK_VK_TO_VSC    = 0
_MAPVK_VSC_TO_VK_EX = 3

# ── Key name ↔ VK ↔ scan code ─────────────────────────────────────────────────

_VK_NAMES: dict[int, str] = {
    0x08: 'backspace', 0x09: 'tab',      0x0D: 'enter',     0x14: 'caps_lock',
    0x1B: 'esc',       0x20: 'space',    0x21: 'page_up',   0x22: 'page_down',
    0x23: 'end',       0x24: 'home',     0x25: 'left',      0x26: 'up',
    0x27: 'right',     0x28: 'down',     0x2C: 'print_screen',
    0x2D: 'insert',    0x2E: 'delete',
    0x5B: 'cmd',       0x5C: 'cmd',
    0x91: 'scroll_lock',
    0x10: 'shift',     0xA0: 'shift',    0xA1: 'shift',
    0x11: 'ctrl',      0xA2: 'ctrl',     0xA3: 'ctrl',
    0x12: 'alt',       0xA4: 'alt',      0xA5: 'alt',
    **{0x70 + i: f'f{i + 1}' for i in range(12)},
    0xAD: 'media_volume_mute',
    0xB3: 'media_play_pause',
    0xB0: 'media_next',
    0xB1: 'media_prev',
}


def _vk_to_name(vk: int) -> Optional[str]:
    if 0x41 <= vk <= 0x5A:
        return chr(vk + 32)
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    return _VK_NAMES.get(vk)


# name → VK reverse map (built once at import time)
_NAME_TO_VK: dict[str, int] = {}

for _vk in range(256):
    _n = _vk_to_name(_vk)
    if _n and _n not in _NAME_TO_VK:
        _NAME_TO_VK[_n] = _vk


def name_to_scan_code(name: str) -> Optional[int]:
    """Return the PS/2 make code for a key name, or None if unknown."""
    vk = _NAME_TO_VK.get(name)
    if vk is None:
        return None
    sc = _u32.MapVirtualKeyW(vk, _MAPVK_VK_TO_VSC)
    return sc if sc != 0 else None


def scan_code_to_name(make_code: int, flags: int) -> Optional[str]:
    """Convert a (MakeCode, Flags) pair from the driver back to a key name."""
    sc = make_code
    if flags & KEY_E0:
        sc |= 0x100  # extended-key hint for MAPVK_VSC_TO_VK_EX
    vk = _u32.MapVirtualKeyW(sc, _MAPVK_VSC_TO_VK_EX)
    if vk == 0:
        return None
    return _vk_to_name(vk)


# ── Client ────────────────────────────────────────────────────────────────────

DEVICE_PATH = r"\\.\SynaplessFilter"


class KbfiltrClient:
    """
    Synchronous client for kbfiltr.sys.

    read_events() blocks; run it in a dedicated daemon thread.
    Closing the handle from another thread will unblock ReadFile and stop the loop.
    """

    def __init__(self):
        self._handle: Optional[int] = None

    @property
    def is_open(self) -> bool:
        return self._handle is not None

    def open(self) -> bool:
        """
        Open \\.\SynaplessFilter.
        Returns True on success, False if the driver is not loaded.
        """
        h = _k32.CreateFileW(
            DEVICE_PATH,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if h == _INVALID_HANDLE:
            err = ctypes.get_last_error()
            log.debug("Cannot open %s (error %d) — kernel filter not active", DEVICE_PATH, err)
            return False
        self._handle = h
        log.info("Opened kernel filter device %s", DEVICE_PATH)
        return True

    def set_macro_keys(self, names: set) -> bool:
        """
        Send the macro key set to the driver as a PS/2 scan code array.
        Passing an empty set clears the driver's suppression list.
        Returns True on success.
        """
        if not self._handle:
            return False

        codes: list[int] = []
        for name in names:
            sc = name_to_scan_code(name)
            if sc is not None:
                codes.append(sc)
            else:
                log.debug("No scan code for key %r — skipping", name)

        if len(codes) > SYNAPLESS_MAX_MACRO_KEYS:
            log.warning("Macro key list exceeds driver limit — truncating to %d",
                        SYNAPLESS_MAX_MACRO_KEYS)
            codes = codes[:SYNAPLESS_MAX_MACRO_KEYS]

        if codes:
            ArrType = ctypes.c_ushort * len(codes)
            buf    = ArrType(*codes)
            in_ptr = ctypes.cast(buf, ctypes.c_void_p)
            in_sz  = ctypes.sizeof(ctypes.c_ushort) * len(codes)
        else:
            in_ptr = None
            in_sz  = 0

        bytes_ret = ctypes.wintypes.DWORD(0)
        ok = _k32.DeviceIoControl(
            self._handle,
            IOCTL_SYNAPLESS_SET_MACRO_KEYS,
            in_ptr, in_sz,
            None, 0,
            ctypes.byref(bytes_ret),
            None,
        )
        if not ok:
            log.error("SET_MACRO_KEYS IOCTL failed (error %d)", ctypes.get_last_error())
            return False
        log.debug("Sent %d macro scan code(s) to driver", len(codes))
        return True

    def read_events(self) -> Generator[Tuple[str, bool], None, None]:
        """
        Blocking generator — yields (key_name, is_keyup) for each driver event.
        Returns when the handle is closed or a read error occurs.
        """
        if not self._handle:
            return

        event    = _KeyEvent()
        evt_size = ctypes.sizeof(_KeyEvent)
        n_read   = ctypes.wintypes.DWORD(0)

        while self._handle:
            ok = _k32.ReadFile(
                self._handle,
                ctypes.byref(event),
                evt_size,
                ctypes.byref(n_read),
                None,
            )
            if not ok or n_read.value != evt_size:
                err = ctypes.get_last_error()
                if self._handle is None or err == 0:
                    break  # clean close
                log.error("ReadFile from kbfiltr failed (error %d)", err)
                break

            name = scan_code_to_name(event.MakeCode, event.Flags)
            if name is None:
                log.debug("Unknown event: MakeCode=0x%02X Flags=0x%02X",
                          event.MakeCode, event.Flags)
                continue
            yield name, bool(event.Flags & KEY_BREAK)

    def close(self):
        if self._handle:
            h = self._handle
            self._handle = None  # signals read_events loop to stop
            _k32.CloseHandle(h)
            log.info("Closed kernel filter device")

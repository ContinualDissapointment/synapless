"""
Macro engine — maps keypresses to configurable action sequences.

Modes:
  once       — fire once per keypress
  hold       — spam while key is held, stop on release
  toggle     — press to start spamming, press again to stop
  start_stop — plays a recorded sequence once; press again to interrupt
               Sequence format: "ctrl+c:150, f5:80, enter"
               where :N is the delay in ms after that keystroke

Architecture (Windows):
  _RawInputWindow runs in its own thread with RIDEV_INPUTSINK and receives
  WM_INPUT for every physical keypress, including the originating hDevice.
  _KeyHook installs WH_KEYBOARD_LL in a second thread.

  Critical constraint: suppressing a key in WH_KEYBOARD_LL (returning non-zero)
  prevents Windows from posting WM_INPUT for that key to any window, regardless
  of thread.  We therefore use stale-data discrimination:

    1. WM_INPUT fires when the hook passes through (first Tartarus press per idle
       period) → records _tartarus_keys[vk] = timestamp + fires macro callback.
    2. On subsequent presses, the hook finds a fresh entry in _tartarus_keys,
       suppresses the key, fires the macro itself, and refreshes the entry.

  Consequence: the very first Tartarus press after a >1s idle period will also
  type the trigger key (e.g. "1" then "q").  Every press after that is clean.
  Regular-keyboard presses of the same key that arrive within 1s of a Tartarus
  press are (rarely) suppressed; presses outside that window pass through.
"""

import ctypes
import ctypes.wintypes
import json
import logging
import os
import pathlib
import threading
import time as _time
from typing import Optional

log = logging.getLogger(__name__)

CONFIG_DIR = pathlib.Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "synapless"
MACRO_FILE = CONFIG_DIR / "macros.json"

try:
    from pynput import keyboard as _kb
    _CTRL = _kb.Controller()
    _PYNPUT = True
except Exception as _e:
    _PYNPUT = False
    _kb = None
    _CTRL = None
    log.warning("pynput unavailable — macros disabled (%s)", _e)

# ── Key injection helpers ──────────────────────────────────────────────────────

_SPECIALS: dict = {}

def _build_specials():
    if not _PYNPUT:
        return
    global _SPECIALS
    _SPECIALS = {
        'ctrl': _kb.Key.ctrl, 'alt': _kb.Key.alt, 'shift': _kb.Key.shift,
        'win': _kb.Key.cmd, 'cmd': _kb.Key.cmd, 'super': _kb.Key.cmd,
        'enter': _kb.Key.enter, 'return': _kb.Key.enter,
        'space': _kb.Key.space, 'tab': _kb.Key.tab,
        'esc': _kb.Key.esc, 'escape': _kb.Key.esc,
        'backspace': _kb.Key.backspace, 'delete': _kb.Key.delete,
        'up': _kb.Key.up, 'down': _kb.Key.down,
        'left': _kb.Key.left, 'right': _kb.Key.right,
        'home': _kb.Key.home, 'end': _kb.Key.end,
        'page_up': _kb.Key.page_up, 'page_down': _kb.Key.page_down,
        'insert': _kb.Key.insert, 'print_screen': _kb.Key.print_screen,
        **{f'f{i}': getattr(_kb.Key, f'f{i}') for i in range(1, 13)},
    }

_build_specials()


def _parse_key(name: str):
    n = name.strip().lower()
    if n in _SPECIALS:
        return _SPECIALS[n]
    s = name.strip()
    if len(s) == 1:
        return s
    return _kb.KeyCode.from_char(s) if _PYNPUT else None


def _fire_combo(combo: str):
    """Press and release a single combo like 'ctrl+c' or 'f5'."""
    keys = [_parse_key(k) for k in combo.split('+')]
    keys = [k for k in keys if k is not None]
    if not keys:
        return
    for k in keys[:-1]:
        _CTRL.press(k)
    _CTRL.press(keys[-1])
    _CTRL.release(keys[-1])
    for k in reversed(keys[:-1]):
        _CTRL.release(k)


def _send(sequence: str):
    """Execute a comma-separated sequence like 'ctrl+c, ctrl+v' or 'f5'."""
    if not _PYNPUT or not _CTRL:
        return
    for part in sequence.split(','):
        part = part.strip()
        if not part:
            continue
        _fire_combo(part)


def _play_recorded(seq: str, stop_event: threading.Event):
    """Play a timing-encoded sequence: 'ctrl+c:150, f5:80, enter'.
    The :N suffix is the delay in ms after firing that keystroke."""
    if not _PYNPUT or not _CTRL:
        return
    for part in seq.split(','):
        if stop_event.is_set():
            break
        part = part.strip()
        if not part:
            continue
        delay_ms = 0
        last_colon = part.rfind(':')
        if last_colon != -1:
            maybe_delay = part[last_colon + 1:]
            if maybe_delay.isdigit():
                delay_ms = int(maybe_delay)
                part = part[:last_colon].strip()
        _fire_combo(part)
        if delay_ms > 0:
            stop_event.wait(delay_ms / 1000.0)


# ── WH_KEYBOARD_LL + Raw Input (Windows) ─────────────────────────────────────

WH_KEYBOARD_LL  = 13
WM_KEYDOWN      = 0x0100
WM_KEYUP        = 0x0101
WM_SYSKEYDOWN   = 0x0104
WM_SYSKEYUP     = 0x0105
HC_ACTION       = 0
LLKHF_INJECTED  = 0x00000010
WM_QUIT         = 0x0012
WM_INPUT        = 0x00FF

RIDEV_INPUTSINK  = 0x00000100
RIM_TYPEKEYBOARD = 1
RID_INPUT        = 0x10000003
RIDI_DEVICENAME  = 0x20000007
RI_KEY_BREAK     = 0x01

_RAZER_VID_STR = "VID_1532"

# How long (seconds) a recorded Razer keypress stays valid for hook suppression.
# Also doubles as the false-positive window for regular-keyboard suppression.
_TARTARUS_WINDOW = 1.0

# Suppress duplicate WM_INPUT from the second Razer HID interface (same physical press).
_DEDUP_WINDOW = 0.015


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('vkCode',      ctypes.wintypes.DWORD),
        ('scanCode',    ctypes.wintypes.DWORD),
        ('flags',       ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]


class _RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ('usUsagePage', ctypes.c_ushort),
        ('usUsage',     ctypes.c_ushort),
        ('dwFlags',     ctypes.c_ulong),
        ('hwndTarget',  ctypes.wintypes.HWND),
    ]


class _RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ('dwType',  ctypes.c_ulong),
        ('dwSize',  ctypes.c_ulong),
        ('hDevice', ctypes.wintypes.HANDLE),
        ('wParam',  ctypes.wintypes.WPARAM),
    ]


class _RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ('MakeCode',         ctypes.c_ushort),
        ('Flags',            ctypes.c_ushort),
        ('Reserved',         ctypes.c_ushort),
        ('VKey',             ctypes.c_ushort),
        ('Message',          ctypes.c_uint),
        ('ExtraInformation', ctypes.c_ulong),
    ]


class _RAWINPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('keyboard', _RAWKEYBOARD)]
    _anonymous_ = ('_u',)
    _fields_ = [
        ('header', _RAWINPUTHEADER),
        ('_u',     _U),
    ]


class _RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [
        ('hDevice', ctypes.wintypes.HANDLE),
        ('dwType',  ctypes.c_ulong),
    ]


_HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)

_WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.LPARAM,
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)


class _WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize',        ctypes.c_uint),
        ('style',         ctypes.c_uint),
        ('lpfnWndProc',   _WNDPROC),
        ('cbClsExtra',    ctypes.c_int),
        ('cbWndExtra',    ctypes.c_int),
        ('hInstance',     ctypes.wintypes.HANDLE),
        ('hIcon',         ctypes.wintypes.HANDLE),
        ('hCursor',       ctypes.wintypes.HANDLE),
        ('hbrBackground', ctypes.wintypes.HANDLE),
        ('lpszMenuName',  ctypes.wintypes.LPCWSTR),
        ('lpszClassName', ctypes.wintypes.LPCWSTR),
        ('hIconSm',       ctypes.wintypes.HANDLE),
    ]


# Fresh WinDLL handle — separate from ctypes.windll.user32 so pynput's argtypes
# don't interfere with ours.
_u32 = ctypes.WinDLL('user32', use_last_error=True)

_u32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, _HOOKPROC, ctypes.c_void_p, ctypes.wintypes.DWORD]
_u32.SetWindowsHookExW.restype  = ctypes.c_void_p
_u32.CallNextHookEx.argtypes    = [
    ctypes.c_void_p, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
_u32.CallNextHookEx.restype     = ctypes.c_long
_u32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
_u32.UnhookWindowsHookEx.restype  = ctypes.wintypes.BOOL
_u32.GetMessageW.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
_u32.GetMessageW.restype  = ctypes.wintypes.BOOL
_u32.PostThreadMessageW.argtypes = [
    ctypes.wintypes.DWORD, ctypes.c_uint,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
_u32.PostThreadMessageW.restype  = ctypes.wintypes.BOOL

_u32.RegisterClassExW.argtypes = [ctypes.c_void_p]
_u32.RegisterClassExW.restype  = ctypes.c_ushort

_u32.CreateWindowExW.argtypes = [
    ctypes.c_ulong, ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR,
    ctypes.c_ulong,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.wintypes.HWND, ctypes.c_void_p, ctypes.wintypes.HANDLE, ctypes.c_void_p,
]
_u32.CreateWindowExW.restype = ctypes.wintypes.HWND

_u32.DestroyWindow.argtypes = [ctypes.wintypes.HWND]
_u32.DestroyWindow.restype  = ctypes.wintypes.BOOL

_u32.DefWindowProcW.argtypes = [
    ctypes.wintypes.HWND, ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
_u32.DefWindowProcW.restype  = ctypes.wintypes.LPARAM

_u32.RegisterRawInputDevices.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
_u32.RegisterRawInputDevices.restype  = ctypes.wintypes.BOOL

_u32.GetRawInputData.argtypes = [
    ctypes.wintypes.LPARAM, ctypes.c_uint, ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint), ctypes.c_uint,
]
_u32.GetRawInputData.restype = ctypes.c_uint

_u32.GetRawInputDeviceList.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.c_uint,
]
_u32.GetRawInputDeviceList.restype = ctypes.c_uint

_u32.GetRawInputDeviceInfoW.argtypes = [
    ctypes.wintypes.HANDLE, ctypes.c_uint, ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint),
]
_u32.GetRawInputDeviceInfoW.restype = ctypes.c_uint


# Shared state between _RawInputWindow (writer) and _KeyHook (reader).
# vk → monotonic timestamp of the last confirmed Razer keydown for that VK.
_tartarus_keys: dict[int, float] = {}
_tartarus_lock = threading.Lock()

_device_filtering_active = False


# VK code → our internal key name
_VK_NAMES: dict[int, str] = {
    0x08: 'backspace', 0x09: 'tab',   0x0D: 'enter',  0x14: 'caps_lock',
    0x1B: 'esc',       0x20: 'space', 0x21: 'page_up', 0x22: 'page_down',
    0x23: 'end',       0x24: 'home',  0x25: 'left',    0x26: 'up',
    0x27: 'right',     0x28: 'down',  0x2C: 'print_screen',
    0x2D: 'insert',    0x2E: 'delete',
    0x5B: 'cmd',       0x5C: 'cmd',
    0x91: 'scroll_lock',
    0x10: 'shift', 0xA0: 'shift', 0xA1: 'shift',
    0x11: 'ctrl',  0xA2: 'ctrl',  0xA3: 'ctrl',
    0x12: 'alt',   0xA4: 'alt',   0xA5: 'alt',
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


def _find_razer_hdevices() -> set:
    """Return hDevice handles for all Razer keyboard HID interfaces."""
    count = ctypes.c_uint(0)
    entry_sz = ctypes.sizeof(_RAWINPUTDEVICELIST)
    ret = _u32.GetRawInputDeviceList(None, ctypes.byref(count), entry_sz)
    if ret == ctypes.c_uint(-1).value or count.value == 0:
        return set()

    DevList = _RAWINPUTDEVICELIST * count.value
    dev_list = DevList()
    _u32.GetRawInputDeviceList(dev_list, ctypes.byref(count), entry_sz)

    handles: set = set()
    for entry in dev_list:
        if entry.dwType != RIM_TYPEKEYBOARD:
            continue
        name_len = ctypes.c_uint(0)
        _u32.GetRawInputDeviceInfoW(
            entry.hDevice, RIDI_DEVICENAME, None, ctypes.byref(name_len))
        if name_len.value == 0:
            continue
        buf = ctypes.create_unicode_buffer(name_len.value)
        _u32.GetRawInputDeviceInfoW(
            entry.hDevice, RIDI_DEVICENAME, buf, ctypes.byref(name_len))
        if _RAZER_VID_STR in buf.value.upper():
            handles.add(entry.hDevice)
            log.debug("Raw Input: Razer keyboard interface: %s", buf.value)
    return handles


_WND_CLS_NAME = "SynaplessRawInput"


class _RawInputWindow:
    """
    Separate thread: RIDEV_INPUTSINK receiver.

    Receives WM_INPUT for every physical keypress (only when the hook does NOT
    suppress that key, since suppression globally blocks WM_INPUT).

    For Razer device keypresses:
      - Records vk → timestamp in _tartarus_keys (used by the hook on the next press).
      - Fires the macro callback immediately (handles the first-press case where the
        hook passed through without suppressing).

    Deduplication: the Tartarus Pro exposes two keyboard HID interfaces; both send
    WM_INPUT for the same physical button.  We dedup on keydown within _DEDUP_WINDOW.
    """

    def __init__(self, on_press, on_release):
        self._on_press = on_press
        self._on_release = on_release
        self._macro_keys: set = set()
        self._lock = threading.Lock()
        self._hwnd = None
        self._wnd_proc_cb = None
        self._thread: Optional[threading.Thread] = None
        self._thread_id: int = 0
        self._hdevices: set = set()
        self._ready = threading.Event()
        self._last_keydown_fire: dict[int, float] = {}  # vk → last deduped keydown time

    def set_macro_keys(self, keys: set):
        with self._lock:
            self._macro_keys = keys

    def start(self):
        self._thread = threading.Thread(target=self._run, name='RawInput', daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3.0)

    def stop(self):
        if self._thread_id:
            _u32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)

    @property
    def hdevices(self) -> set:
        return self._hdevices

    # ── Thread entry ──────────────────────────────────────────────────────────

    def _run(self):
        global _device_filtering_active
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        hinstance = ctypes.windll.kernel32.GetModuleHandleW(None)

        self._wnd_proc_cb = _WNDPROC(self._wnd_proc)
        wc = _WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(_WNDCLASSEXW)
        wc.lpfnWndProc = self._wnd_proc_cb
        wc.lpszClassName = _WND_CLS_NAME
        wc.hInstance = hinstance

        atom = _u32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            err = ctypes.get_last_error()
            if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                log.error("RegisterClassExW failed (%d) — Raw Input disabled", err)

        self._hwnd = _u32.CreateWindowExW(
            0, _WND_CLS_NAME, _WND_CLS_NAME,
            0, 0, 0, 0, 0,
            None, None, hinstance, None,
        )
        if not self._hwnd:
            log.warning("CreateWindowExW failed (%d) — Raw Input disabled",
                        ctypes.get_last_error())
            self._ready.set()
            return

        self._hdevices = _find_razer_hdevices()
        if self._hdevices:
            rid = _RAWINPUTDEVICE()
            rid.usUsagePage = 0x01
            rid.usUsage     = 0x06
            rid.dwFlags     = RIDEV_INPUTSINK
            rid.hwndTarget  = self._hwnd
            if _u32.RegisterRawInputDevices(
                    ctypes.byref(rid), 1, ctypes.sizeof(_RAWINPUTDEVICE)):
                _device_filtering_active = True
                log.info("Device filtering enabled — %d Razer keyboard interface(s)",
                         len(self._hdevices))
            else:
                log.warning("RegisterRawInputDevices failed (%d) — all-keyboard fallback",
                            ctypes.get_last_error())
        else:
            log.info("No Razer keyboard interfaces found — all-keyboard fallback active")

        self._ready.set()

        msg = ctypes.wintypes.MSG()
        while _u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        if self._hwnd:
            _u32.DestroyWindow(self._hwnd)
            self._hwnd = None
        _device_filtering_active = False

    # ── Window procedure ──────────────────────────────────────────────────────

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            self._process_raw_input(lparam)
        return _u32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _process_raw_input(self, hrawinput: int):
        size = ctypes.c_uint(0)
        hdr_sz = ctypes.sizeof(_RAWINPUTHEADER)
        _u32.GetRawInputData(hrawinput, RID_INPUT, None, ctypes.byref(size), hdr_sz)
        if size.value == 0:
            return
        buf = ctypes.create_string_buffer(size.value)
        read = _u32.GetRawInputData(hrawinput, RID_INPUT, buf, ctypes.byref(size), hdr_sz)
        if read == 0 or read == ctypes.c_uint(-1).value:
            return
        raw = ctypes.cast(buf, ctypes.POINTER(_RAWINPUT)).contents
        if raw.header.dwType != RIM_TYPEKEYBOARD or raw.header.hDevice == 0:
            return

        is_keyup = bool(raw.keyboard.Flags & RI_KEY_BREAK)
        vk       = raw.keyboard.VKey
        name     = _vk_to_name(vk)
        if not name:
            return

        if raw.header.hDevice not in self._hdevices:
            return  # regular keyboard — hook already let it through, nothing to do

        # Razer device: record the press time for the hook to use on the NEXT press,
        # and fire the macro for THIS press (hook passed through = first press per idle).
        now = _time.monotonic()

        if not is_keyup:
            # Dedup: two Razer interfaces fire WM_INPUT for the same physical keydown.
            last = self._last_keydown_fire.get(vk, 0.0)
            if now - last < _DEDUP_WINDOW:
                return
            self._last_keydown_fire[vk] = now

            with _tartarus_lock:
                _tartarus_keys[vk] = now

            threading.Thread(target=self._on_press, args=(name,), daemon=True).start()
        else:
            # Keyup: fire on_release.  No dedup needed — duplicate keyups are harmless
            # (on_release is idempotent for all modes).
            threading.Thread(target=self._on_release, args=(name,), daemon=True).start()


class _KeyHook:
    """
    WH_KEYBOARD_LL hook running in its own thread.

    Uses _tartarus_keys (written by _RawInputWindow on previous presses) to decide
    whether a macro keypress is from the Tartarus (suppress + fire) or a regular
    keyboard (pass through).

    _suppressed_downs tracks which VKs had their keydown suppressed so the matching
    keyup is also suppressed and on_release is called correctly.
    """

    def __init__(self, on_press, on_release):
        self._on_press = on_press
        self._on_release = on_release
        self._macro_keys: set = set()
        self._lock = threading.Lock()
        self._hook = None
        self._proc = None
        self._thread: Optional[threading.Thread] = None
        self._thread_id: int = 0
        # VKs whose keydown was suppressed; keyup must also be suppressed.
        self._suppressed_downs: set[int] = set()

    def set_macro_keys(self, keys: set):
        with self._lock:
            self._macro_keys = keys

    def start(self):
        self._thread = threading.Thread(target=self._run, name='KeyHook', daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread_id:
            _u32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)

    # ── Thread entry ──────────────────────────────────────────────────────────

    def _run(self):
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        self._proc = _HOOKPROC(self._hook_proc)
        self._hook = _u32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        if not self._hook:
            log.error("SetWindowsHookExW failed (error %d)", ctypes.get_last_error())
            return

        msg = ctypes.wintypes.MSG()
        while _u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        _u32.UnhookWindowsHookEx(self._hook)

    # ── Hook procedure ────────────────────────────────────────────────────────

    def _hook_proc(self, code: int, wparam: int, lparam: int) -> int:
        if code == HC_ACTION:
            data = ctypes.cast(lparam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
            is_injected = bool(data.flags & LLKHF_INJECTED)

            if not is_injected:
                vk   = data.vkCode
                name = _vk_to_name(vk)
                if name:
                    with self._lock:
                        is_macro = name in self._macro_keys
                    if is_macro:
                        is_down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                        is_up   = wparam in (WM_KEYUP,   WM_SYSKEYUP)

                        if _device_filtering_active:
                            if is_down:
                                now = _time.monotonic()
                                with _tartarus_lock:
                                    t = _tartarus_keys.get(vk, 0.0)
                                if now - t < _TARTARUS_WINDOW:
                                    # Previous WM_INPUT confirmed Tartarus pressed this VK.
                                    # Suppress and fire; refresh so next press also works.
                                    self._suppressed_downs.add(vk)
                                    with _tartarus_lock:
                                        _tartarus_keys[vk] = now
                                    threading.Thread(
                                        target=self._on_press, args=(name,),
                                        daemon=True).start()
                                    return 1
                                # No (fresh) Razer record → pass through.
                                # _RawInputWindow will receive WM_INPUT and handle it.

                            elif is_up:
                                if vk in self._suppressed_downs:
                                    self._suppressed_downs.discard(vk)
                                    threading.Thread(
                                        target=self._on_release, args=(name,),
                                        daemon=True).start()
                                    return 1
                                # Keydown wasn't suppressed → let keyup through too.

                        else:
                            # No device filtering — fire for any physical keyboard.
                            if is_down:
                                threading.Thread(
                                    target=self._on_press, args=(name,),
                                    daemon=True).start()
                            elif is_up:
                                threading.Thread(
                                    target=self._on_release, args=(name,),
                                    daemon=True).start()
                            return 1

        return _u32.CallNextHookEx(None, code, wparam, lparam)


# ── Manager ────────────────────────────────────────────────────────────────────

class MacroManager:
    def __init__(self):
        self._macros: dict = {}
        self._active: set = set()
        self._threads: dict = {}
        self._lock = threading.Lock()
        self._raw_win: Optional[_RawInputWindow] = None
        self._hook: Optional[_KeyHook] = None
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── Persistence ───────────────────────────────────────────────

    def _load(self):
        if MACRO_FILE.exists():
            try:
                self._macros = json.loads(MACRO_FILE.read_text(encoding='utf-8'))
            except Exception as e:
                log.warning("Failed to load macros: %s", e)

    def _save(self):
        MACRO_FILE.write_text(json.dumps(self._macros, indent=2), encoding='utf-8')

    def _sync_hook_keys(self):
        keys = set(self._macros.keys())
        if self._raw_win:
            self._raw_win.set_macro_keys(keys)
        if self._hook:
            self._hook.set_macro_keys(keys)

    # ── Public API ────────────────────────────────────────────────

    def get_all(self) -> dict:
        with self._lock:
            return dict(self._macros)

    def set_macro(self, key: str, sequence: str, mode: str,
                  interval_ms: int = 50, record_timing: bool = False):
        with self._lock:
            self._macros[key] = {
                'sequence': sequence,
                'mode': mode,
                'interval_ms': interval_ms,
                'record_timing': record_timing,
            }
            self._save()
        self._sync_hook_keys()

    def delete_macro(self, key: str):
        self._stop_thread(key)
        with self._lock:
            self._macros.pop(key, None)
            self._active.discard(key)
            self._save()
        self._sync_hook_keys()

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self):
        if not _PYNPUT:
            log.warning("Macros disabled — pynput not available")
            return
        self._raw_win = _RawInputWindow(self._on_press, self._on_release)
        self._hook    = _KeyHook(self._on_press, self._on_release)
        self._sync_hook_keys()
        self._raw_win.start()   # blocks until window created + RIDEV registered
        self._hook.start()
        log.info("MacroManager started")

    def stop(self):
        if self._hook:
            self._hook.stop()
        if self._raw_win:
            self._raw_win.stop()
        for key in list(self._threads):
            self._stop_thread(key)

    # ── Handlers ─────────────────────────────────────────────────

    def _on_press(self, name: str):
        with self._lock:
            macro = self._macros.get(name)
        if not macro:
            return
        mode     = macro.get('mode', 'once')
        seq      = macro.get('sequence', '')
        interval = macro.get('interval_ms', 50) / 1000.0

        if mode == 'once':
            threading.Thread(target=_send, args=(seq,), daemon=True).start()
        elif mode == 'hold':
            if name not in self._threads:
                self._start_spam(name, seq, interval)
        elif mode == 'toggle':
            if name in self._active:
                self._active.discard(name)
                self._stop_thread(name)
            else:
                self._active.add(name)
                self._start_spam(name, seq, interval)
        elif mode == 'start_stop':
            if name in self._active:
                self._active.discard(name)
                self._stop_thread(name)
            else:
                self._active.add(name)
                stop = threading.Event()
                self._threads[name] = stop
                def _play(n=name, s=seq, ev=stop):
                    _play_recorded(s, ev)
                    self._active.discard(n)
                    self._threads.pop(n, None)
                threading.Thread(target=_play, daemon=True).start()

    def _on_release(self, name: str):
        with self._lock:
            macro = self._macros.get(name)
        if macro and macro.get('mode') == 'hold':
            self._stop_thread(name)

    # ── Spam ──────────────────────────────────────────────────────

    def _start_spam(self, key: str, seq: str, interval: float):
        stop = threading.Event()
        self._threads[key] = stop
        def _loop():
            while not stop.is_set():
                _send(seq)
                stop.wait(interval)
        threading.Thread(target=_loop, daemon=True).start()

    def _stop_thread(self, key: str):
        evt = self._threads.pop(key, None)
        if evt:
            evt.set()

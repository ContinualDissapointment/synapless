"""
Macro engine — maps keypresses to configurable action sequences.

Modes:
  once       — fire once per keypress
  hold       — spam while key is held, stop on release
  toggle     — press to start spamming, press again to stop
  start_stop — plays a recorded sequence once; press again to interrupt
               Sequence format: "ctrl+c:150, f5:80, enter"
               where :N is the delay in ms after that keystroke

Uses a raw WH_KEYBOARD_LL ctypes hook instead of pynput's Listener so that:
  - Physical presses on macro keys are suppressed (trigger key doesn't type itself)
  - Injected keystrokes (from macro playback) are detected via LLKHF_INJECTED
    and passed through without re-triggering the macro
"""

import ctypes
import ctypes.wintypes
import json
import logging
import os
import pathlib
import threading
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


# ── WH_KEYBOARD_LL hook (Windows) ─────────────────────────────────────────────

WH_KEYBOARD_LL  = 13
WM_KEYDOWN      = 0x0100
WM_KEYUP        = 0x0101
WM_SYSKEYDOWN   = 0x0104
WM_SYSKEYUP     = 0x0105
HC_ACTION       = 0
LLKHF_INJECTED  = 0x00000010
WM_QUIT         = 0x0012

class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('vkCode',      ctypes.wintypes.DWORD),
        ('scanCode',    ctypes.wintypes.DWORD),
        ('flags',       ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]

_HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)

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

# VK code → our internal key name
_VK_NAMES: dict[int, str] = {
    0x08: 'backspace', 0x09: 'tab',   0x0D: 'enter',  0x14: 'caps_lock',
    0x1B: 'esc',       0x20: 'space', 0x21: 'page_up', 0x22: 'page_down',
    0x23: 'end',       0x24: 'home',  0x25: 'left',    0x26: 'up',
    0x27: 'right',     0x28: 'down',  0x2C: 'print_screen',
    0x2D: 'insert',    0x2E: 'delete',
    0x5B: 'cmd',       0x5C: 'cmd',   # left/right Win
    0x91: 'scroll_lock',
    # Modifier generic VK codes (sent by some devices)
    0x10: 'shift', 0xA0: 'shift', 0xA1: 'shift',
    0x11: 'ctrl',  0xA2: 'ctrl',  0xA3: 'ctrl',
    0x12: 'alt',   0xA4: 'alt',   0xA5: 'alt',
    # F1–F12
    **{0x70 + i: f'f{i + 1}' for i in range(12)},
    # Media
    0xAD: 'media_volume_mute',
    0xB3: 'media_play_pause',
    0xB0: 'media_next',
    0xB1: 'media_prev',
}

def _vk_to_name(vk: int) -> Optional[str]:
    if 0x41 <= vk <= 0x5A:
        return chr(vk + 32)   # A–Z → a–z
    if 0x30 <= vk <= 0x39:
        return chr(vk)         # 0–9
    return _VK_NAMES.get(vk)


class _KeyHook:
    """
    Low-level keyboard hook that selectively suppresses physical keypresses
    for keys that have macros assigned, while passing injected events through.
    """

    def __init__(self, on_press, on_release):
        self._on_press = on_press
        self._on_release = on_release
        self._macro_keys: set = set()
        self._lock = threading.Lock()
        self._hook = None
        self._proc = None   # CFUNCTYPE ref — must stay alive
        self._thread: Optional[threading.Thread] = None
        self._thread_id: int = 0

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

    def _hook_proc(self, code: int, wparam: int, lparam: int) -> int:
        if code == HC_ACTION:
            data = ctypes.cast(lparam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
            is_injected = bool(data.flags & LLKHF_INJECTED)

            if not is_injected:
                name = _vk_to_name(data.vkCode)
                if name:
                    with self._lock:
                        is_macro = name in self._macro_keys
                    if is_macro:
                        if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                            threading.Thread(
                                target=self._on_press, args=(name,), daemon=True).start()
                        elif wparam in (WM_KEYUP, WM_SYSKEYUP):
                            threading.Thread(
                                target=self._on_release, args=(name,), daemon=True).start()
                        return 1  # suppress — event never reaches the active window

        return _u32.CallNextHookEx(None, code, wparam, lparam)


# ── Manager ────────────────────────────────────────────────────────────────────

class MacroManager:
    def __init__(self):
        self._macros: dict = {}
        self._active: set = set()
        self._threads: dict = {}
        self._lock = threading.Lock()
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
        if self._hook:
            self._hook.set_macro_keys(set(self._macros.keys()))

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
        self._hook = _KeyHook(self._on_press, self._on_release)
        self._sync_hook_keys()
        self._hook.start()
        log.info("MacroManager started")

    def stop(self):
        if self._hook:
            self._hook.stop()
        for key in list(self._threads):
            self._stop_thread(key)

    # ── Handlers (receive key name string, not pynput object) ────

    def _on_press(self, name: str):
        with self._lock:
            macro = self._macros.get(name)
        if not macro:
            return
        mode = macro.get('mode', 'once')
        seq = macro.get('sequence', '')
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

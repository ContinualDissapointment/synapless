"""
driver_install.py — install / uninstall / query kbfiltr.sys.

All functions that modify system state require elevation (run as Administrator).

CLI usage:
    python -m service.driver_install install
    python -m service.driver_install uninstall
    python -m service.driver_install status
    python -m service.driver_install testsign    # enable test-signing mode (needs reboot)
"""

import ctypes
import ctypes.wintypes
import logging
import pathlib
import re
import subprocess
import sys
from typing import Optional

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

# service/ → project root → driver/kbfiltr/
_SERVICE_DIR = pathlib.Path(__file__).parent
_DRIVER_DIR  = _SERVICE_DIR.parent / "driver" / "kbfiltr"
_INF_PATH    = _DRIVER_DIR / "kbfiltr.inf"
_SYS_PATH    = _DRIVER_DIR / "kbfiltr.sys"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=check,
    )


def is_elevated() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


# ── Device open check ─────────────────────────────────────────────────────────

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_k32.CreateFileW.restype  = ctypes.wintypes.HANDLE
_k32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.wintypes.HANDLE,
]
_k32.CloseHandle.restype  = ctypes.wintypes.BOOL
_k32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

_INVALID_HANDLE  = ctypes.wintypes.HANDLE(-1).value
GENERIC_READ     = 0x80000000
GENERIC_WRITE    = 0x40000000
FILE_SHARE_RW    = 0x00000003
OPEN_EXISTING    = 3
FILE_ATTRIBUTE_NORMAL = 0x80
DEVICE_PATH      = r"\\.\SynaplessFilter"


def is_driver_loaded() -> bool:
    """Return True if kbfiltr.sys is running and the control device is reachable."""
    h = _k32.CreateFileW(
        DEVICE_PATH,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_RW,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if h == _INVALID_HANDLE:
        return False
    _k32.CloseHandle(h)
    return True


# ── pnputil wrappers ──────────────────────────────────────────────────────────

def _find_oem_inf() -> Optional[str]:
    """Return the OEM INF name (e.g. 'oem42.inf') staged for kbfiltr, or None."""
    try:
        result = _run(["pnputil", "/enum-drivers"])
        # pnputil output has blocks like:
        #   Published Name:     oem42.inf
        #   Original Name:      kbfiltr.inf
        blocks = result.stdout.split("\n\n")
        for block in blocks:
            if "kbfiltr.inf" in block.lower():
                for line in block.splitlines():
                    m = re.match(r"Published Name\s*:\s*(oem\d+\.inf)", line, re.IGNORECASE)
                    if m:
                        return m.group(1)
    except Exception as e:
        log.debug("pnputil enum-drivers failed: %s", e)
    return None


def install_driver(inf_path: Optional[pathlib.Path] = None) -> bool:
    """
    Stage and install kbfiltr.inf via pnputil.
    Requires elevation and test-signing mode (or attestation-signed driver).
    Returns True on success.
    """
    if not is_elevated():
        log.error("install_driver requires elevation (run as Administrator)")
        return False

    inf = inf_path or _INF_PATH
    if not inf.exists():
        log.error("INF not found: %s", inf)
        return False
    if not _SYS_PATH.exists():
        log.error("kbfiltr.sys not found: %s", _SYS_PATH)
        return False

    log.info("Installing driver from %s ...", inf)
    try:
        result = _run([
            "pnputil", "/add-driver", str(inf), "/install", "/subdirs",
        ], check=False)
        log.debug("pnputil stdout: %s", result.stdout.strip())
        if result.returncode not in (0, 259):  # 259 = ERROR_NO_MORE_ITEMS (no matching device yet)
            log.error("pnputil failed (rc=%d): %s", result.returncode, result.stderr.strip())
            return False
        log.info("Driver installed successfully")
        return True
    except FileNotFoundError:
        log.error("pnputil not found — is this Windows?")
        return False


def uninstall_driver() -> bool:
    """
    Remove kbfiltr from the driver store and all matched devices.
    Requires elevation.
    """
    if not is_elevated():
        log.error("uninstall_driver requires elevation")
        return False

    oem = _find_oem_inf()
    if not oem:
        log.info("kbfiltr driver not found in driver store — nothing to remove")
        return True

    log.info("Removing driver %s ...", oem)
    try:
        result = _run([
            "pnputil", "/delete-driver", oem, "/uninstall", "/force",
        ], check=False)
        if result.returncode != 0:
            log.error("pnputil delete-driver failed (rc=%d): %s",
                      result.returncode, result.stderr.strip())
            return False
        log.info("Driver removed")
        return True
    except FileNotFoundError:
        log.error("pnputil not found")
        return False


def driver_store_info() -> dict:
    """Return a dict with staged OEM INF name and whether the device is reachable."""
    return {
        "oem_inf":  _find_oem_inf(),
        "loaded":   is_driver_loaded(),
        "inf_path": str(_INF_PATH),
        "sys_path": str(_SYS_PATH),
        "sys_exists": _SYS_PATH.exists(),
    }


# ── Test-signing mode ─────────────────────────────────────────────────────────

def enable_test_signing() -> bool:
    """
    Enable Windows test-signing boot option (bcdedit /set testsigning on).
    Requires elevation.  A reboot is required for the change to take effect.
    """
    if not is_elevated():
        log.error("enable_test_signing requires elevation")
        return False
    try:
        result = _run(["bcdedit", "/set", "testsigning", "on"], check=False)
        if result.returncode != 0:
            log.error("bcdedit failed (rc=%d): %s", result.returncode, result.stderr.strip())
            return False
        log.info("Test-signing enabled — reboot required")
        return True
    except FileNotFoundError:
        log.error("bcdedit not found")
        return False


def is_test_signing_on() -> bool:
    try:
        result = _run(["bcdedit", "/enum", "{current}"], check=False)
        return "testsigning" in result.stdout.lower() and "yes" in result.stdout.lower()
    except Exception:
        return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        info = driver_store_info()
        print(f"kbfiltr.sys built : {info['sys_exists']}  ({info['sys_path']})")
        print(f"Staged OEM INF    : {info['oem_inf'] or '(not staged)'}")
        print(f"Device reachable  : {info['loaded']}")
        print(f"Test signing      : {'on' if is_test_signing_on() else 'off'}")

    elif cmd == "install":
        ok = install_driver()
        sys.exit(0 if ok else 1)

    elif cmd == "uninstall":
        ok = uninstall_driver()
        sys.exit(0 if ok else 1)

    elif cmd == "testsign":
        ok = enable_test_signing()
        if ok:
            print("Test-signing enabled.  Reboot now to apply.")
        sys.exit(0 if ok else 1)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

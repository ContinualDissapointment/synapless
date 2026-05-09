"""
driver_install.py — install / uninstall / query kbfiltr.sys.

Uses direct SCM registration + registry UpperFilters update.  Does NOT use
pnputil (which requires a signed/cataloged driver even in test-signing mode).
Test-signing mode IS required; without it the kernel refuses to load the driver.

All functions that modify system state require elevation (run as Administrator).

CLI usage:
    python -m service.driver_install testsign    # enable test-signing (reboot required)
    python -m service.driver_install install     # copy .sys, register service, set UpperFilters
    python -m service.driver_install uninstall   # undo everything
    python -m service.driver_install status      # check current state
"""

import ctypes
import ctypes.wintypes
import logging
import pathlib
import shutil
import subprocess
import sys
import winreg
from typing import Optional

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_SERVICE_DIR = pathlib.Path(__file__).parent
_DRIVER_DIR  = _SERVICE_DIR.parent / "driver" / "kbfiltr"
_SYS_SRC     = _DRIVER_DIR / "kbfiltr.sys"
_SYS_DEST    = pathlib.Path(r"C:\Windows\System32\drivers\kbfiltr.sys")

_SERVICE_NAME    = "kbfiltr"
_SERVICE_DISPLAY = "Synapless Keyboard Filter"

# Razer Tartarus Pro — both HID keyboard interfaces
_RAZER_HW_IDS = [
    "VID_1532&PID_0244&MI_00",
    "VID_1532&PID_0244&MI_01",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(args: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=check)


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

_INVALID_HANDLE = ctypes.wintypes.HANDLE(-1).value
DEVICE_PATH = r"\\.\SynaplessFilter"


def is_driver_loaded() -> bool:
    """Return True if kbfiltr.sys is running and \\.\SynaplessFilter is reachable."""
    h = _k32.CreateFileW(
        DEVICE_PATH, 0xC0000000, 0x03, None, 3, 0x80, None,
    )
    if h == _INVALID_HANDLE:
        return False
    _k32.CloseHandle(h)
    return True


# ── Registry helpers ──────────────────────────────────────────────────────────

def _enum_device_instances(hw_id_suffix: str) -> list[str]:
    """
    Return full registry paths of device instances whose hardware ID list
    contains the given hw_id_suffix (e.g. 'VID_1532&PID_0244&MI_00').
    """
    base = r"SYSTEM\CurrentControlSet\Enum\HID"
    results = []
    try:
        hive = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
    except OSError:
        return results

    suffix_upper = hw_id_suffix.upper()
    i = 0
    while True:
        try:
            dev_id = winreg.EnumKey(hive, i)
        except OSError:
            break
        i += 1
        if suffix_upper not in dev_id.upper():
            continue
        try:
            dev_key = winreg.OpenKey(hive, dev_id)
        except OSError:
            continue
        j = 0
        while True:
            try:
                inst_id = winreg.EnumKey(dev_key, j)
            except OSError:
                break
            j += 1
            results.append(rf"{base}\{dev_id}\{inst_id}")
        winreg.CloseKey(dev_key)
    winreg.CloseKey(hive)
    return results


def _get_upper_filters(inst_path: str) -> list[str]:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, inst_path)
        val, _ = winreg.QueryValueEx(key, "UpperFilters")
        winreg.CloseKey(key)
        return list(val) if val else []
    except OSError:
        return []


def _set_upper_filters(inst_path: str, values: list[str]):
    key = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE, inst_path,
        0, winreg.KEY_SET_VALUE,
    )
    winreg.SetValueEx(key, "UpperFilters", 0, winreg.REG_MULTI_SZ, values)
    winreg.CloseKey(key)


# ── SCM service management ────────────────────────────────────────────────────

def _sc(*args) -> tuple[int, str]:
    """Run sc.exe and return (returncode, stdout+stderr)."""
    r = _run(["sc"] + list(args))
    out = (r.stdout + r.stderr).strip()
    return r.returncode, out


def _service_exists() -> bool:
    rc, _ = _sc("query", _SERVICE_NAME)
    return rc == 0


def _create_service() -> bool:
    rc, out = _sc(
        "create", _SERVICE_NAME,
        "type=", "kernel",
        "start=", "demand",
        "error=", "normal",
        "binpath=", str(_SYS_DEST),
        "displayname=", _SERVICE_DISPLAY,
        "group=", "Keyboard Port",
    )
    if rc != 0:
        log.error("sc create failed (rc=%d): %s", rc, out)
        return False
    return True


def _delete_service() -> bool:
    rc, out = _sc("delete", _SERVICE_NAME)
    if rc != 0 and "1060" not in out:  # 1060 = service does not exist
        log.error("sc delete failed (rc=%d): %s", rc, out)
        return False
    return True


# ── Public API ────────────────────────────────────────────────────────────────

def install_driver() -> bool:
    """
    Copy kbfiltr.sys → System32\\drivers, register the SCM service, and
    add 'kbfiltr' to UpperFilters for each matched Tartarus device instance.

    Requires elevation and test-signing mode.
    After install the Tartarus must be unplugged and replugged once.
    """
    if not is_elevated():
        log.error("install_driver requires elevation (run as Administrator)")
        return False
    if not _SYS_SRC.exists():
        log.error("kbfiltr.sys not found at %s — build it first (cd driver/kbfiltr && build.bat)", _SYS_SRC)
        return False

    # 1. Copy driver binary
    log.info("Copying %s → %s", _SYS_SRC, _SYS_DEST)
    try:
        shutil.copy2(_SYS_SRC, _SYS_DEST)
    except PermissionError as e:
        log.error("Cannot copy driver: %s", e)
        return False

    # 2. Register SCM service (idempotent)
    if _service_exists():
        log.info("Service '%s' already exists — skipping sc create", _SERVICE_NAME)
    else:
        log.info("Creating SCM service '%s'", _SERVICE_NAME)
        if not _create_service():
            return False

    # 3. Add kbfiltr to UpperFilters for each Tartarus device instance
    found_any = False
    for hw_id in _RAZER_HW_IDS:
        for inst_path in _enum_device_instances(hw_id):
            found_any = True
            filters = _get_upper_filters(inst_path)
            if _SERVICE_NAME in filters:
                log.info("UpperFilters already set for %s", inst_path)
                continue
            filters.append(_SERVICE_NAME)
            try:
                _set_upper_filters(inst_path, filters)
                log.info("Set UpperFilters on %s → %s", inst_path, filters)
            except PermissionError as e:
                log.error("Cannot write UpperFilters for %s: %s", inst_path, e)
                return False

    if not found_any:
        log.warning(
            "No Tartarus Pro device instances found in registry. "
            "Plug in the device, then re-run install."
        )
    else:
        log.info(
            "Install complete.  Unplug and replug the Tartarus Pro to load the filter."
        )
    return True


def uninstall_driver() -> bool:
    """Remove UpperFilters entries, delete the SCM service, and remove the .sys file."""
    if not is_elevated():
        log.error("uninstall_driver requires elevation")
        return False

    # 1. Remove UpperFilters
    for hw_id in _RAZER_HW_IDS:
        for inst_path in _enum_device_instances(hw_id):
            filters = _get_upper_filters(inst_path)
            if _SERVICE_NAME not in filters:
                continue
            filters = [f for f in filters if f != _SERVICE_NAME]
            try:
                _set_upper_filters(inst_path, filters)
                log.info("Removed kbfiltr from UpperFilters: %s", inst_path)
            except PermissionError as e:
                log.error("Cannot update UpperFilters for %s: %s", inst_path, e)

    # 2. Delete service
    log.info("Deleting SCM service '%s'", _SERVICE_NAME)
    _delete_service()

    # 3. Remove .sys
    if _SYS_DEST.exists():
        try:
            _SYS_DEST.unlink()
            log.info("Removed %s", _SYS_DEST)
        except PermissionError:
            log.warning(
                "Cannot remove %s while driver is loaded — reboot and retry uninstall",
                _SYS_DEST,
            )

    log.info("Uninstall complete.  Replug the Tartarus Pro to restore normal operation.")
    return True


def driver_status() -> dict:
    instances: list[str] = []
    for hw_id in _RAZER_HW_IDS:
        instances.extend(_enum_device_instances(hw_id))

    filtered = [p for p in instances if _SERVICE_NAME in _get_upper_filters(p)]
    return {
        "sys_built":         _SYS_SRC.exists(),
        "sys_deployed":      _SYS_DEST.exists(),
        "service_exists":    _service_exists(),
        "device_loaded":     is_driver_loaded(),
        "device_instances":  instances,
        "filtered_instances": filtered,
        "test_signing":      _is_test_signing_on(),
    }


# ── Test-signing mode ─────────────────────────────────────────────────────────

def enable_test_signing() -> bool:
    """bcdedit /set testsigning on — requires elevation + reboot."""
    if not is_elevated():
        log.error("enable_test_signing requires elevation")
        return False
    r = _run(["bcdedit", "/set", "testsigning", "on"])
    if r.returncode != 0:
        log.error("bcdedit failed: %s", (r.stdout + r.stderr).strip())
        return False
    log.info("Test-signing enabled.  Reboot to apply.")
    return True


def _is_test_signing_on() -> bool:
    r = _run(["bcdedit", "/enum", "{current}"])
    text = r.stdout.lower()
    return "testsigning" in text and "yes" in text


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        s = driver_status()
        print(f"kbfiltr.sys built      : {s['sys_built']}  ({_SYS_SRC})")
        print(f"kbfiltr.sys deployed   : {s['sys_deployed']}  ({_SYS_DEST})")
        print(f"SCM service exists     : {s['service_exists']}")
        print(f"Device reachable       : {s['device_loaded']}")
        print(f"Test signing           : {'on' if s['test_signing'] else 'off'}")
        print(f"Device instances found : {len(s['device_instances'])}")
        print(f"  filtered by kbfiltr  : {len(s['filtered_instances'])}")
        for p in s['filtered_instances']:
            print(f"    {p}")

    elif cmd == "install":
        sys.exit(0 if install_driver() else 1)

    elif cmd == "uninstall":
        sys.exit(0 if uninstall_driver() else 1)

    elif cmd == "testsign":
        ok = enable_test_signing()
        if ok:
            print("Reboot now, then run:  python -m service.driver_install install")
        sys.exit(0 if ok else 1)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

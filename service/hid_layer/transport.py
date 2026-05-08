"""
Windows HID transport — wraps the `hid` (hidapi) library.

On Windows, Razer devices expose multiple HID interfaces per physical device.
The "control" interface used for RGB/config feature reports is typically:
  usage_page = 0x0001, usage = 0x0002  (generic desktop / mouse-like)

We try that first, then fall back to interface_number == 2, then 1.
The service must run elevated (Administrator) so Windows allows feature-report
access on these interfaces.
"""

import os
import time
import logging
from typing import Optional

# Ensure hidapi.dll (bundled in the project root) is found on Windows
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(_ROOT)

try:
    import hid
except ImportError:  # allow import on non-Windows dev machines
    hid = None  # type: ignore

from .protocol import RazerReport, REPORT_LEN, RAZER_VENDOR_ID

log = logging.getLogger(__name__)

# How long to wait after sending before reading the response (seconds).
# The Linux driver uses usb_control_msg with a 500ms timeout.
SEND_DELAY = 0.005   # 5 ms is enough for most commands
MAX_RETRIES = 3

# Preferred control interface characteristics (ordered, first match wins).
_IFACE_PREFERENCES: list[dict] = [
    {"usage_page": 0x0001, "usage": 0x0002},   # generic desktop / gamepad-like
    {"usage_page": 0x0001, "usage": 0x0006},   # generic desktop / keyboard
    {"interface_number": 2},
    {"interface_number": 1},
]


def _find_control_path(vid: int, pid: int) -> Optional[str]:
    """Return the HID path of the best control interface for (vid, pid)."""
    if hid is None:
        raise RuntimeError("hid library not installed — run: pip install hid")

    devices = hid.enumerate(vid, pid)
    if not devices:
        return None

    for pref in _IFACE_PREFERENCES:
        for dev in devices:
            if all(dev.get(k) == v for k, v in pref.items()):
                return dev["path"]

    # Last resort: pick the last interface (usually vendor-specific)
    return devices[-1]["path"]


class HIDTransport:
    """
    Thin wrapper around a single opened HID device.
    Thread-safety: the caller (DeviceManager) must serialize access.
    """

    def __init__(self, vid: int, pid: int):
        self.vid = vid
        self.pid = pid
        self._device = None
        self._path: Optional[str] = None

    def open(self) -> None:
        path = _find_control_path(self.vid, self.pid)
        if path is None:
            raise IOError(f"No HID path found for {self.vid:04X}:{self.pid:04X}")
        dev = hid.Device(path=path)
        self._device = dev
        self._path = path
        log.debug("Opened HID %04X:%04X path=%s", self.vid, self.pid, path)

    def close(self) -> None:
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None

    def send(self, report: RazerReport) -> Optional[RazerReport]:
        """
        Send a report and read back the response.
        Returns the response RazerReport, or None on timeout/error.
        """
        if self._device is None:
            raise IOError("HID device is not open")

        payload = report.to_bytes()
        # HIDAPI send_feature_report prepends the report-ID byte (0x00 for Razer).
        buf = bytes([0x00]) + payload

        for attempt in range(MAX_RETRIES):
            try:
                written = self._device.send_feature_report(buf)
                if written < 0:
                    log.warning("send_feature_report returned %d (attempt %d)", written, attempt)
                    continue

                time.sleep(SEND_DELAY)

                # Read response: same layout, report-ID stripped by hidapi.
                resp_raw = self._device.get_feature_report(0x00, REPORT_LEN + 1)
                if resp_raw and len(resp_raw) >= REPORT_LEN:
                    # hidapi may include a leading report-ID byte
                    data = bytes(resp_raw[1:]) if len(resp_raw) > REPORT_LEN else bytes(resp_raw)
                    return RazerReport.from_bytes(data)

                log.debug("Empty response on attempt %d", attempt)
            except OSError as exc:
                log.warning("HID I/O error (attempt %d): %s", attempt, exc)
                time.sleep(0.02)

        log.error("No valid response after %d attempts for class=0x%02X id=0x%02X",
                  MAX_RETRIES, report.command_class, report.command_id)
        return None

    def send_no_response(self, report: RazerReport) -> bool:
        """Send without reading back (for fire-and-forget commands like custom frames)."""
        if self._device is None:
            raise IOError("HID device is not open")
        buf = bytes([0x00]) + report.to_bytes()
        return self._device.send_feature_report(buf) >= 0

    @property
    def is_open(self) -> bool:
        return self._device is not None

    def reopen(self) -> None:
        self.close()
        self.open()


def enumerate_razer_devices() -> list[dict]:
    """
    Return list of dicts describing every unique (vid, pid) pair currently
    connected for Razer VID 0x1532.
    """
    if hid is None:
        raise RuntimeError("hid library not installed")

    seen: dict[int, dict] = {}
    for dev in hid.enumerate(RAZER_VENDOR_ID, 0):
        pid = dev["product_id"]
        if pid not in seen:
            seen[pid] = {
                "vid": dev["vendor_id"],
                "pid": pid,
                "manufacturer": dev.get("manufacturer_string", "Razer"),
                "product": dev.get("product_string", f"Unknown ({pid:04X})"),
            }
    return list(seen.values())

"""
DeviceManager — discovers connected Razer devices and keeps them alive.

Runs a background thread that re-scans every RESCAN_INTERVAL seconds so
hot-plug works without restarting the service.
"""

import logging
import threading
import time
from typing import Dict, Optional, Type

from .hid_layer.transport import HIDTransport, enumerate_razer_devices
from .hardware import get_device_class
from .hardware.device_base import RazerDevice

log = logging.getLogger(__name__)

RESCAN_INTERVAL = 5.0  # seconds between plug/unplug checks


class ManagedDevice:
    def __init__(self, device: RazerDevice, transport: HIDTransport):
        self.device = device
        self.transport = transport


class DeviceManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._devices: Dict[str, ManagedDevice] = {}   # keyed by serial
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._scan()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        log.info("DeviceManager started, %d device(s) found", len(self._devices))

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        with self._lock:
            for md in self._devices.values():
                md.transport.close()
            self._devices.clear()
        log.info("DeviceManager stopped")

    def _watch_loop(self) -> None:
        while not self._stop.wait(RESCAN_INTERVAL):
            self._scan()

    # ── Scanning ──────────────────────────────────────────────────────────────

    def _scan(self) -> None:
        try:
            found = enumerate_razer_devices()
        except Exception as exc:
            log.error("Device enumeration failed: %s", exc)
            return

        current_pids = {info["pid"] for info in found}

        with self._lock:
            # Remove devices that disconnected
            gone = [
                serial for serial, md in self._devices.items()
                if md.device.USB_PID not in current_pids
            ]
            for serial in gone:
                log.info("Device disconnected: %s", serial)
                self._devices[serial].transport.close()
                del self._devices[serial]

            # Add newly connected devices
            existing_pids = {md.device.USB_PID for md in self._devices.values()}
            for info in found:
                pid = info["pid"]
                if pid in existing_pids:
                    continue

                cls = get_device_class(pid)
                if cls is None:
                    log.debug("Unsupported Razer device PID=0x%04X (%s)", pid, info["product"])
                    continue

                try:
                    transport = HIDTransport(info["vid"], pid)
                    transport.open()
                    device = cls(transport, product_string=info["product"])
                    serial = device.serial
                    self._devices[serial] = ManagedDevice(device, transport)
                    log.info("Device connected: %s (0x%04X) serial=%s", info["product"], pid, serial)
                except Exception as exc:
                    log.warning("Failed to open 0x%04X %s: %s", pid, info["product"], exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def list_devices(self) -> list[dict]:
        with self._lock:
            return [md.device.get_device_info() for md in self._devices.values()]

    def get_device(self, serial: str) -> Optional[RazerDevice]:
        with self._lock:
            md = self._devices.get(serial)
            return md.device if md else None

    def get_all(self) -> list[RazerDevice]:
        with self._lock:
            return [md.device for md in self._devices.values()]

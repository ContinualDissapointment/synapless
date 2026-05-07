"""
Base class for all Razer devices on Windows.

Subclasses declare USB_PID, METHODS, HAS_MATRIX, etc. as class attributes
(same layout as upstream openrazer daemon hardware files so syncing is easy).
All protocol I/O goes through self._transport (HIDTransport).
"""

import logging
from typing import Optional, TYPE_CHECKING

from ..hid_layer import protocol as proto
from ..hid_layer import effects as fx
from ..hid_layer.protocol import BACKLIGHT_LED, LOGO_LED, SCROLL_WHEEL_LED, VARSTORE

if TYPE_CHECKING:
    from ..hid_layer.transport import HIDTransport

log = logging.getLogger(__name__)

DEVICE_TYPES = {
    "keyboard": "keyboard",
    "mouse": "mouse",
    "mousemat": "mousemat",
    "headset": "headset",
    "accessory": "accessory",
}


class RazerDevice:
    # ── Subclass must set these ───────────────────────────────────────────────
    USB_VID: int = proto.RAZER_VENDOR_ID
    USB_PID: int | None = None
    METHODS: list[str] = []
    HAS_MATRIX: bool = False
    MATRIX_DIMS: list[int] | None = None
    DPI_MAX: int | None = None
    DEVICE_TYPE: str = "accessory"   # keyboard | mouse | mousemat | headset | accessory

    # Whether this device uses extended (0x0F) vs standard (0x03) effects
    USE_EXTENDED_EFFECTS: bool = True

    # LED IDs used by this device (subclasses override as needed)
    BACKLIGHT_LED_ID: int = BACKLIGHT_LED
    LOGO_LED_ID: int = LOGO_LED
    SCROLL_LED_ID: int = SCROLL_WHEEL_LED

    # ── Instance ──────────────────────────────────────────────────────────────

    def __init__(self, transport: "HIDTransport", product_string: str = ""):
        self._transport = transport
        self._product_string = product_string
        self._serial: Optional[str] = None
        self._firmware: Optional[str] = None

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def serial(self) -> str:
        if self._serial is None:
            self._serial = self._read_serial()
        return self._serial or f"{self.USB_PID:04X}"

    @property
    def firmware_version(self) -> str:
        if self._firmware is None:
            self._firmware = self._read_firmware()
        return self._firmware or "unknown"

    def _read_serial(self) -> Optional[str]:
        resp = self._transport.send(proto.report_get_serial())
        if resp is None:
            return None
        try:
            return bytes(resp.arguments[:22]).decode("ascii").rstrip("\x00")
        except Exception:
            return None

    def _read_firmware(self) -> Optional[str]:
        resp = self._transport.send(proto.report_get_firmware_version())
        if resp is None:
            return None
        return f"v{resp.arguments[0]}.{resp.arguments[1]}"

    def get_device_info(self) -> dict:
        return {
            "pid": self.USB_PID,
            "serial": self.serial,
            "firmware": self.firmware_version,
            "product": self._product_string,
            "type": self.DEVICE_TYPE,
            "has_matrix": self.HAS_MATRIX,
            "matrix_dims": self.MATRIX_DIMS,
            "dpi_max": self.DPI_MAX,
            "methods": self.METHODS,
        }

    # ── Brightness ────────────────────────────────────────────────────────────

    def get_brightness(self) -> float:
        if self.USE_EXTENDED_EFFECTS:
            resp = self._transport.send(fx.ext_get_brightness(self.BACKLIGHT_LED_ID))
        else:
            resp = self._transport.send(fx.standard_get_brightness(self.BACKLIGHT_LED_ID))
        if resp is None:
            return 100.0
        raw = resp.arguments[2] if self.USE_EXTENDED_EFFECTS else resp.arguments[2]
        return round(raw / 255 * 100, 1)

    def set_brightness(self, brightness_pct: float) -> bool:
        raw = int(max(0, min(100, brightness_pct)) / 100 * 255)
        if self.USE_EXTENDED_EFFECTS:
            r = fx.ext_brightness(self.BACKLIGHT_LED_ID, raw)
        else:
            r = fx.standard_set_brightness(self.BACKLIGHT_LED_ID, raw)
        return self._transport.send_no_response(r)

    # ── Generic lighting helpers ───────────────────────────────────────────────

    def _led_id_for_zone(self, zone: str) -> int:
        return {
            "backlight": self.BACKLIGHT_LED_ID,
            "logo": self.LOGO_LED_ID,
            "scroll": self.SCROLL_LED_ID,
        }.get(zone, self.BACKLIGHT_LED_ID)

    def _send_effect(self, report) -> bool:
        return self._transport.send_no_response(report)

    # ── Static ────────────────────────────────────────────────────────────────

    def set_static_effect(self, r: int, g: int, b: int, zone: str = "backlight") -> bool:
        led = self._led_id_for_zone(zone)
        if self.USE_EXTENDED_EFFECTS:
            return self._send_effect(fx.ext_static(led, (r, g, b)))
        return self._send_effect(fx.standard_static(led, (r, g, b)))

    # ── None ──────────────────────────────────────────────────────────────────

    def set_none_effect(self, zone: str = "backlight") -> bool:
        led = self._led_id_for_zone(zone)
        if self.USE_EXTENDED_EFFECTS:
            return self._send_effect(fx.ext_none(led))
        return self._send_effect(fx.standard_none(led))

    # ── Spectrum ──────────────────────────────────────────────────────────────

    def set_spectrum_effect(self, zone: str = "backlight") -> bool:
        led = self._led_id_for_zone(zone)
        if self.USE_EXTENDED_EFFECTS:
            return self._send_effect(fx.ext_spectrum(led))
        return self._send_effect(fx.standard_spectrum(led))

    # ── Wave ──────────────────────────────────────────────────────────────────

    def set_wave_effect(self, direction: int = 1, zone: str = "backlight") -> bool:
        led = self._led_id_for_zone(zone)
        if self.USE_EXTENDED_EFFECTS:
            return self._send_effect(fx.ext_wave(led, direction))
        return self._send_effect(fx.standard_wave(led, direction))

    # ── Reactive ──────────────────────────────────────────────────────────────

    def set_reactive_effect(self, speed: int, r: int, g: int, b: int, zone: str = "backlight") -> bool:
        led = self._led_id_for_zone(zone)
        if self.USE_EXTENDED_EFFECTS:
            return self._send_effect(fx.ext_reactive(led, speed, (r, g, b)))
        return self._send_effect(fx.standard_reactive(led, speed, (r, g, b)))

    # ── Breathing ─────────────────────────────────────────────────────────────

    def set_breath_random_effect(self, zone: str = "backlight") -> bool:
        led = self._led_id_for_zone(zone)
        if self.USE_EXTENDED_EFFECTS:
            return self._send_effect(fx.ext_breathing_random(led))
        return self._send_effect(fx.standard_breathing_random(led))

    def set_breath_single_effect(self, r: int, g: int, b: int, zone: str = "backlight") -> bool:
        led = self._led_id_for_zone(zone)
        if self.USE_EXTENDED_EFFECTS:
            return self._send_effect(fx.ext_breathing_single(led, (r, g, b)))
        return self._send_effect(fx.standard_breathing_single(led, (r, g, b)))

    def set_breath_dual_effect(
        self, r1: int, g1: int, b1: int, r2: int, g2: int, b2: int, zone: str = "backlight"
    ) -> bool:
        led = self._led_id_for_zone(zone)
        if self.USE_EXTENDED_EFFECTS:
            return self._send_effect(fx.ext_breathing_dual(led, (r1, g1, b1), (r2, g2, b2)))
        return self._send_effect(fx.standard_breathing_dual(led, (r1, g1, b1), (r2, g2, b2)))

    # ── Starlight ─────────────────────────────────────────────────────────────

    def set_starlight_random_effect(self, speed: int = 1, zone: str = "backlight") -> bool:
        led = self._led_id_for_zone(zone)
        return self._send_effect(fx.ext_starlight_random(led, speed))

    def set_starlight_single_effect(self, speed: int, r: int, g: int, b: int, zone: str = "backlight") -> bool:
        led = self._led_id_for_zone(zone)
        return self._send_effect(fx.ext_starlight_single(led, speed, (r, g, b)))

    def set_starlight_dual_effect(
        self, speed: int, r1: int, g1: int, b1: int, r2: int, g2: int, b2: int, zone: str = "backlight"
    ) -> bool:
        led = self._led_id_for_zone(zone)
        return self._send_effect(fx.ext_starlight_dual(led, speed, (r1, g1, b1), (r2, g2, b2)))

    # ── Custom matrix ─────────────────────────────────────────────────────────

    def set_custom_effect(self) -> bool:
        if self.USE_EXTENDED_EFFECTS:
            return self._send_effect(fx.ext_custom_frame())
        r = proto.get_report(0x03, 0x0A, 0x02)
        r.arguments[0] = self.BACKLIGHT_LED_ID
        r.arguments[1] = proto.EFFECT_CUSTOMFRAME
        return self._send_effect(r)

    def set_key_row(self, row_id: int, start_col: int, stop_col: int, rgb_data: bytes) -> bool:
        if self.USE_EXTENDED_EFFECTS:
            r = fx.matrix_set_custom_frame_extended(row_id, start_col, stop_col, rgb_data)
        else:
            r = fx.matrix_set_custom_frame(row_id, start_col, stop_col, rgb_data)
        return self._send_effect(r)

    # ── DPI (mice) ────────────────────────────────────────────────────────────

    def get_dpi_xy(self) -> tuple[int, int]:
        resp = self._transport.send(proto.report_get_dpi_xy())
        if resp is None:
            return (800, 800)
        return proto.parse_dpi_xy(resp)

    def set_dpi_xy(self, dpi_x: int, dpi_y: int) -> bool:
        if self.DPI_MAX:
            dpi_x = min(dpi_x, self.DPI_MAX)
            dpi_y = min(dpi_y, self.DPI_MAX)
        return self._transport.send_no_response(proto.report_set_dpi_xy(dpi_x, dpi_y))

    def max_dpi(self) -> int:
        return self.DPI_MAX or 16000

    # ── Polling rate ──────────────────────────────────────────────────────────

    def get_poll_rate(self) -> int:
        resp = self._transport.send(proto.report_get_polling_rate())
        if resp is None:
            return 500
        return proto.parse_polling_rate(resp)

    def set_poll_rate(self, hz: int) -> bool:
        return self._transport.send_no_response(proto.report_set_polling_rate(hz))

    # ── Battery ───────────────────────────────────────────────────────────────

    def get_battery(self) -> float:
        resp = self._transport.send(proto.report_get_battery_level())
        if resp is None:
            return -1.0
        return proto.parse_battery_level(resp)

    def is_charging(self) -> bool:
        resp = self._transport.send(proto.report_get_charging_status())
        if resp is None:
            return False
        return proto.parse_charging_status(resp)

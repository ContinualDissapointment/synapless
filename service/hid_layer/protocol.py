"""
Razer USB HID protocol — ported from driver/razercommon.h and razercommon.c.

Report layout (90 bytes):
  [0]     status          0x00 = new request
  [1]     transaction_id  0xFF default
  [2-3]   remaining_packets (big-endian, always 0x0000)
  [4]     protocol_type   0x00
  [5]     data_size       number of meaningful argument bytes
  [6]     command_class
  [7]     command_id
  [8-87]  arguments       (80 bytes)
  [88]    crc             XOR of bytes [2..87]
  [89]    reserved        0x00
"""

import struct
from dataclasses import dataclass, field
from typing import Sequence

RAZER_VENDOR_ID = 0x1532
REPORT_LEN = 90
ARGS_LEN = 80
ARGS_OFFSET = 8

# variable_storage values
VARSTORE = 0x01   # persist across reboot
NOSTORE  = 0x00   # volatile

# LED IDs  (from razercommon.h)
SCROLL_WHEEL_LED  = 0x01
BATTERY_LED       = 0x03
LOGO_LED          = 0x04
BACKLIGHT_LED     = 0x05
MACRO_LED         = 0x07
GAME_LED          = 0x08
RED_PROFILE_LED   = 0x0C
GREEN_PROFILE_LED = 0x0D
BLUE_PROFILE_LED  = 0x0E
RIGHT_SIDE_LED    = 0x10
LEFT_SIDE_LED     = 0x11

# Effect IDs for standard (0x03, 0x0A) commands
EFFECT_NONE        = 0x00
EFFECT_WAVE        = 0x01
EFFECT_REACTIVE    = 0x02
EFFECT_BREATHING   = 0x03
EFFECT_SPECTRUM    = 0x04
EFFECT_CUSTOMFRAME = 0x05
EFFECT_STATIC      = 0x06
EFFECT_STARLIGHT   = 0x19

# Extended effect IDs (0x0F, 0x02)
EXT_EFFECT_NONE      = 0x00
EXT_EFFECT_STATIC    = 0x01
EXT_EFFECT_BREATHING = 0x02
EXT_EFFECT_SPECTRUM  = 0x03
EXT_EFFECT_WAVE      = 0x04
EXT_EFFECT_REACTIVE  = 0x05
EXT_EFFECT_STARLIGHT = 0x07
EXT_EFFECT_CUSTOM    = 0x08
EXT_EFFECT_WHEEL     = 0x0A


def _clamp_u8(value: int) -> int:
    return max(0, min(255, int(value)))


def _clamp_u16(value: int, lo: int = 100, hi: int = 45000) -> int:
    return max(lo, min(hi, int(value)))


@dataclass
class RazerReport:
    command_class: int
    command_id: int
    data_size: int
    arguments: bytearray = field(default_factory=lambda: bytearray(ARGS_LEN))
    transaction_id: int = 0xFF
    status: int = 0x00

    def to_bytes(self) -> bytes:
        buf = bytearray(REPORT_LEN)
        buf[0] = self.status
        buf[1] = self.transaction_id
        buf[2] = 0x00  # remaining_packets high
        buf[3] = 0x00  # remaining_packets low
        buf[4] = 0x00  # protocol_type
        buf[5] = self.data_size
        buf[6] = self.command_class
        buf[7] = self.command_id
        buf[ARGS_OFFSET:ARGS_OFFSET + ARGS_LEN] = self.arguments[:ARGS_LEN]
        buf[88] = _crc(buf)
        buf[89] = 0x00
        return bytes(buf)

    @classmethod
    def from_bytes(cls, data: bytes | bytearray) -> "RazerReport":
        if len(data) < REPORT_LEN:
            raise ValueError(f"Response too short: {len(data)} < {REPORT_LEN}")
        r = cls(
            command_class=data[6],
            command_id=data[7],
            data_size=data[5],
            transaction_id=data[1],
            status=data[0],
        )
        r.arguments = bytearray(data[ARGS_OFFSET:ARGS_OFFSET + ARGS_LEN])
        return r


def _crc(buf: bytearray) -> int:
    result = 0
    for i in range(2, 88):
        result ^= buf[i]
    return result


def get_report(command_class: int, command_id: int, data_size: int) -> RazerReport:
    return RazerReport(command_class=command_class, command_id=command_id, data_size=data_size)


# ── Info / misc queries ───────────────────────────────────────────────────────

def report_get_serial() -> RazerReport:
    return get_report(0x00, 0x82, 0x16)


def report_get_firmware_version() -> RazerReport:
    return get_report(0x00, 0x81, 0x02)


def report_get_device_mode() -> RazerReport:
    return get_report(0x00, 0x84, 0x02)


def report_set_device_mode(mode: int, param: int) -> RazerReport:
    r = get_report(0x00, 0x04, 0x02)
    r.arguments[0] = mode
    r.arguments[1] = param
    return r


# ── Polling rate ──────────────────────────────────────────────────────────────

_POLL_RATE_MAP = {1000: 0x01, 500: 0x02, 250: 0x04, 125: 0x08}
_POLL_RATE_INV = {v: k for k, v in _POLL_RATE_MAP.items()}


def report_set_polling_rate(hz: int) -> RazerReport:
    r = get_report(0x00, 0x05, 0x01)
    r.arguments[0] = _POLL_RATE_MAP.get(hz, 0x02)
    return r


def report_get_polling_rate() -> RazerReport:
    return get_report(0x00, 0x85, 0x01)


def parse_polling_rate(response: RazerReport) -> int:
    return _POLL_RATE_INV.get(response.arguments[0], 500)


# ── DPI ───────────────────────────────────────────────────────────────────────

def report_set_dpi_xy(dpi_x: int, dpi_y: int, variable_storage: int = VARSTORE) -> RazerReport:
    dpi_x = _clamp_u16(dpi_x)
    dpi_y = _clamp_u16(dpi_y)
    r = get_report(0x04, 0x05, 0x07)
    r.arguments[0] = variable_storage
    r.arguments[1] = (dpi_x >> 8) & 0xFF
    r.arguments[2] = dpi_x & 0xFF
    r.arguments[3] = (dpi_y >> 8) & 0xFF
    r.arguments[4] = dpi_y & 0xFF
    r.arguments[5] = 0x00
    r.arguments[6] = 0x00
    return r


def report_get_dpi_xy(variable_storage: int = VARSTORE) -> RazerReport:
    r = get_report(0x04, 0x85, 0x07)
    r.arguments[0] = variable_storage
    return r


def parse_dpi_xy(response: RazerReport) -> tuple[int, int]:
    dpi_x = (response.arguments[1] << 8) | response.arguments[2]
    dpi_y = (response.arguments[3] << 8) | response.arguments[4]
    return dpi_x, dpi_y


# ── Battery ───────────────────────────────────────────────────────────────────

def report_get_battery_level() -> RazerReport:
    return get_report(0x07, 0x80, 0x02)


def report_get_charging_status() -> RazerReport:
    return get_report(0x07, 0x84, 0x02)


def parse_battery_level(response: RazerReport) -> float:
    # Returns 0–100 percent
    raw = response.arguments[1]
    return round(raw / 255 * 100, 1)


def parse_charging_status(response: RazerReport) -> bool:
    return response.arguments[1] == 0x01

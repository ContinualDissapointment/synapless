"""
Lighting effect report builders — ported from driver/razerchromacommon.c.

Two families:
  standard  — command class 0x03, used by older/simpler devices
  extended  — command class 0x0F, used by most modern Chroma devices

Each function returns a ready-to-send RazerReport (CRC not yet applied;
transport.send() finalises it).
"""

from .protocol import (
    RazerReport, get_report, _clamp_u8,
    VARSTORE, NOSTORE,
    BACKLIGHT_LED, LOGO_LED, SCROLL_WHEEL_LED,
    EFFECT_NONE, EFFECT_WAVE, EFFECT_REACTIVE, EFFECT_BREATHING,
    EFFECT_SPECTRUM, EFFECT_CUSTOMFRAME, EFFECT_STATIC, EFFECT_STARLIGHT,
    EXT_EFFECT_NONE, EXT_EFFECT_STATIC, EXT_EFFECT_BREATHING,
    EXT_EFFECT_SPECTRUM, EXT_EFFECT_WAVE, EXT_EFFECT_REACTIVE,
    EXT_EFFECT_STARLIGHT, EXT_EFFECT_CUSTOM, EXT_EFFECT_WHEEL,
)


RGB = tuple[int, int, int]


# ── Standard effects (class 0x03) ─────────────────────────────────────────────

def standard_set_effect(led_id: int, effect_id: int) -> RazerReport:
    r = get_report(0x03, 0x0A, 0x02)
    r.arguments[0] = led_id
    r.arguments[1] = effect_id
    return r


def standard_set_led_rgb(led_id: int, rgb: RGB) -> RazerReport:
    r = get_report(0x03, 0x01, 0x05)
    r.arguments[0] = VARSTORE
    r.arguments[1] = led_id
    r.arguments[2] = _clamp_u8(rgb[0])
    r.arguments[3] = _clamp_u8(rgb[1])
    r.arguments[4] = _clamp_u8(rgb[2])
    return r


def standard_set_brightness(led_id: int, brightness: int) -> RazerReport:
    r = get_report(0x03, 0x03, 0x03)
    r.arguments[0] = VARSTORE
    r.arguments[1] = led_id
    r.arguments[2] = _clamp_u8(brightness)
    return r


def standard_get_brightness(led_id: int) -> RazerReport:
    r = get_report(0x03, 0x83, 0x03)
    r.arguments[0] = VARSTORE
    r.arguments[1] = led_id
    return r


def standard_none(led_id: int) -> RazerReport:
    return standard_set_effect(led_id, EFFECT_NONE)


def standard_static(led_id: int, rgb: RGB) -> RazerReport:
    r = get_report(0x03, 0x0A, 0x05)
    r.arguments[0] = led_id
    r.arguments[1] = EFFECT_STATIC
    r.arguments[2] = _clamp_u8(rgb[0])
    r.arguments[3] = _clamp_u8(rgb[1])
    r.arguments[4] = _clamp_u8(rgb[2])
    return r


def standard_spectrum(led_id: int) -> RazerReport:
    return standard_set_effect(led_id, EFFECT_SPECTRUM)


def standard_wave(led_id: int, direction: int) -> RazerReport:
    r = get_report(0x03, 0x0A, 0x03)
    r.arguments[0] = led_id
    r.arguments[1] = EFFECT_WAVE
    r.arguments[2] = max(1, min(2, direction))
    return r


def standard_reactive(led_id: int, speed: int, rgb: RGB) -> RazerReport:
    r = get_report(0x03, 0x0A, 0x06)
    r.arguments[0] = led_id
    r.arguments[1] = EFFECT_REACTIVE
    r.arguments[2] = _clamp_u8(speed)
    r.arguments[3] = _clamp_u8(rgb[0])
    r.arguments[4] = _clamp_u8(rgb[1])
    r.arguments[5] = _clamp_u8(rgb[2])
    return r


def standard_breathing_random(led_id: int) -> RazerReport:
    r = get_report(0x03, 0x0A, 0x03)
    r.arguments[0] = led_id
    r.arguments[1] = EFFECT_BREATHING
    r.arguments[2] = 0x03  # random
    return r


def standard_breathing_single(led_id: int, rgb: RGB) -> RazerReport:
    r = get_report(0x03, 0x0A, 0x06)
    r.arguments[0] = led_id
    r.arguments[1] = EFFECT_BREATHING
    r.arguments[2] = 0x01  # single colour
    r.arguments[3] = _clamp_u8(rgb[0])
    r.arguments[4] = _clamp_u8(rgb[1])
    r.arguments[5] = _clamp_u8(rgb[2])
    return r


def standard_breathing_dual(led_id: int, rgb1: RGB, rgb2: RGB) -> RazerReport:
    r = get_report(0x03, 0x0A, 0x09)
    r.arguments[0] = led_id
    r.arguments[1] = EFFECT_BREATHING
    r.arguments[2] = 0x02  # dual colour
    r.arguments[3] = _clamp_u8(rgb1[0])
    r.arguments[4] = _clamp_u8(rgb1[1])
    r.arguments[5] = _clamp_u8(rgb1[2])
    r.arguments[6] = _clamp_u8(rgb2[0])
    r.arguments[7] = _clamp_u8(rgb2[1])
    r.arguments[8] = _clamp_u8(rgb2[2])
    return r


# ── Extended effects (class 0x0F) ─────────────────────────────────────────────

def _ext_base(arg_size: int, variable_storage: int, led_id: int, effect_id: int) -> RazerReport:
    r = get_report(0x0F, 0x02, arg_size)
    r.arguments[0] = variable_storage
    r.arguments[1] = led_id
    r.arguments[2] = effect_id
    return r


def ext_none(led_id: int, variable_storage: int = VARSTORE) -> RazerReport:
    return _ext_base(0x06, variable_storage, led_id, EXT_EFFECT_NONE)


def ext_static(led_id: int, rgb: RGB, variable_storage: int = VARSTORE) -> RazerReport:
    r = _ext_base(0x09, variable_storage, led_id, EXT_EFFECT_STATIC)
    r.arguments[5] = 0x01
    r.arguments[6] = _clamp_u8(rgb[0])
    r.arguments[7] = _clamp_u8(rgb[1])
    r.arguments[8] = _clamp_u8(rgb[2])
    return r


def ext_spectrum(led_id: int, variable_storage: int = VARSTORE) -> RazerReport:
    return _ext_base(0x06, variable_storage, led_id, EXT_EFFECT_SPECTRUM)


def ext_wave(led_id: int, direction: int, variable_storage: int = VARSTORE) -> RazerReport:
    r = _ext_base(0x06, variable_storage, led_id, EXT_EFFECT_WAVE)
    r.arguments[3] = max(1, min(2, direction))
    r.arguments[4] = 0x28  # speed (lower = faster)
    return r


def ext_reactive(led_id: int, speed: int, rgb: RGB, variable_storage: int = VARSTORE) -> RazerReport:
    r = _ext_base(0x09, variable_storage, led_id, EXT_EFFECT_REACTIVE)
    r.arguments[4] = max(1, min(4, speed))
    r.arguments[5] = 0x01
    r.arguments[6] = _clamp_u8(rgb[0])
    r.arguments[7] = _clamp_u8(rgb[1])
    r.arguments[8] = _clamp_u8(rgb[2])
    return r


def ext_breathing_random(led_id: int, variable_storage: int = VARSTORE) -> RazerReport:
    return _ext_base(0x06, variable_storage, led_id, EXT_EFFECT_BREATHING)


def ext_breathing_single(led_id: int, rgb: RGB, variable_storage: int = VARSTORE) -> RazerReport:
    r = _ext_base(0x09, variable_storage, led_id, EXT_EFFECT_BREATHING)
    r.arguments[3] = 0x01
    r.arguments[5] = 0x01
    r.arguments[6] = _clamp_u8(rgb[0])
    r.arguments[7] = _clamp_u8(rgb[1])
    r.arguments[8] = _clamp_u8(rgb[2])
    return r


def ext_breathing_dual(led_id: int, rgb1: RGB, rgb2: RGB, variable_storage: int = VARSTORE) -> RazerReport:
    r = _ext_base(0x0C, variable_storage, led_id, EXT_EFFECT_BREATHING)
    r.arguments[3] = 0x02
    r.arguments[5] = 0x02
    r.arguments[6]  = _clamp_u8(rgb1[0])
    r.arguments[7]  = _clamp_u8(rgb1[1])
    r.arguments[8]  = _clamp_u8(rgb1[2])
    r.arguments[9]  = _clamp_u8(rgb2[0])
    r.arguments[10] = _clamp_u8(rgb2[1])
    r.arguments[11] = _clamp_u8(rgb2[2])
    return r


def ext_starlight_random(led_id: int, speed: int, variable_storage: int = VARSTORE) -> RazerReport:
    r = _ext_base(0x06, variable_storage, led_id, EXT_EFFECT_STARLIGHT)
    r.arguments[4] = max(1, min(3, speed))
    return r


def ext_starlight_single(led_id: int, speed: int, rgb: RGB, variable_storage: int = VARSTORE) -> RazerReport:
    r = _ext_base(0x09, variable_storage, led_id, EXT_EFFECT_STARLIGHT)
    r.arguments[4] = max(1, min(3, speed))
    r.arguments[5] = 0x01
    r.arguments[6] = _clamp_u8(rgb[0])
    r.arguments[7] = _clamp_u8(rgb[1])
    r.arguments[8] = _clamp_u8(rgb[2])
    return r


def ext_starlight_dual(led_id: int, speed: int, rgb1: RGB, rgb2: RGB, variable_storage: int = VARSTORE) -> RazerReport:
    r = _ext_base(0x0C, variable_storage, led_id, EXT_EFFECT_STARLIGHT)
    r.arguments[4]  = max(1, min(3, speed))
    r.arguments[5]  = 0x02
    r.arguments[6]  = _clamp_u8(rgb1[0])
    r.arguments[7]  = _clamp_u8(rgb1[1])
    r.arguments[8]  = _clamp_u8(rgb1[2])
    r.arguments[9]  = _clamp_u8(rgb2[0])
    r.arguments[10] = _clamp_u8(rgb2[1])
    r.arguments[11] = _clamp_u8(rgb2[2])
    return r


def ext_wheel(led_id: int, direction: int, variable_storage: int = VARSTORE) -> RazerReport:
    r = _ext_base(0x06, variable_storage, led_id, EXT_EFFECT_WHEEL)
    r.arguments[3] = max(1, min(2, direction))
    r.arguments[4] = 0x28
    return r


def ext_custom_frame() -> RazerReport:
    return _ext_base(0x0C, 0x00, 0x00, EXT_EFFECT_CUSTOM)


def ext_brightness(led_id: int, brightness: int, variable_storage: int = VARSTORE) -> RazerReport:
    r = get_report(0x0F, 0x04, 0x03)
    r.arguments[0] = variable_storage
    r.arguments[1] = led_id
    r.arguments[2] = _clamp_u8(brightness)
    return r


def ext_get_brightness(led_id: int, variable_storage: int = VARSTORE) -> RazerReport:
    r = get_report(0x0F, 0x84, 0x03)
    r.arguments[0] = variable_storage
    r.arguments[1] = led_id
    return r


# ── Custom matrix frame (per-key RGB) ─────────────────────────────────────────

def matrix_set_custom_frame(row_id: int, start_col: int, stop_col: int, rgb_data: bytes) -> RazerReport:
    """
    Send one row of per-key RGB data.
    rgb_data must be exactly (stop_col - start_col + 1) * 3 bytes.
    """
    num_cols = stop_col - start_col + 1
    assert len(rgb_data) == num_cols * 3, "rgb_data length mismatch"
    data_size = 3 + num_cols * 3
    r = get_report(0x03, 0x0B, data_size)
    r.arguments[0] = row_id
    r.arguments[1] = start_col
    r.arguments[2] = stop_col
    r.arguments[3:3 + len(rgb_data)] = rgb_data
    return r


def matrix_set_custom_frame_extended(row_id: int, start_col: int, stop_col: int, rgb_data: bytes) -> RazerReport:
    """Extended version for devices using 0x0F class."""
    num_cols = stop_col - start_col + 1
    assert len(rgb_data) == num_cols * 3
    data_size = 5 + num_cols * 3
    r = get_report(0x0F, 0x03, data_size)
    r.arguments[0] = 0xFF  # LED ID wildcard
    r.arguments[1] = row_id
    r.arguments[2] = start_col
    r.arguments[3] = stop_col
    r.arguments[4:4 + len(rgb_data)] = rgb_data
    return r

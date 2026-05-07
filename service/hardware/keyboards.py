"""
Keyboard device definitions — mirrors upstream openrazer daemon/hardware/keyboards.py.
Only USB_PID, METHODS, HAS_MATRIX, MATRIX_DIMS, and DEVICE_TYPE are used;
EVENT_FILE_REGEX and D-Bus base-class imports are intentionally omitted.

To add a new device: copy the class block from upstream openrazer and drop it here.
Run scripts/sync_devices.py to do this automatically.
"""

from .device_base import RazerDevice


class _Keyboard(RazerDevice):
    DEVICE_TYPE = "keyboard"
    USE_EXTENDED_EFFECTS = True


class _KeyboardStandard(_Keyboard):
    """Older devices that use the standard (0x03) effect commands."""
    USE_EXTENDED_EFFECTS = False


# ── BlackWidow ────────────────────────────────────────────────────────────────

class RazerBlackWidowChromaV2(_Keyboard):
    USB_PID = 0x0221
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect', 'set_starlight_single_effect', 'set_starlight_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerBlackWidowV3(_Keyboard):
    USB_PID = 0x024E
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect', 'set_starlight_single_effect', 'set_starlight_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerBlackWidowV3Mini(_Keyboard):
    USB_PID = 0x0258
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 18]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerBlackWidowV3TKL(_Keyboard):
    USB_PID = 0x0A24
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 18]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerBlackWidowV3Pro(_Keyboard):
    USB_PID = 0x025A
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect', 'set_starlight_single_effect', 'set_starlight_dual_effect',
               'set_custom_effect', 'set_key_row',
               'get_battery', 'is_charging']


class RazerBlackWidowV4(_Keyboard):
    USB_PID = 0x0287
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect',
               'set_custom_effect', 'set_key_row']


class RazerBlackWidowV4Pro(_Keyboard):
    USB_PID = 0x028D
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerBlackWidowV4X(_Keyboard):
    USB_PID = 0x0289
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


# ── Huntsman ──────────────────────────────────────────────────────────────────

class RazerHuntsman(_Keyboard):
    USB_PID = 0x0227
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect', 'set_starlight_single_effect', 'set_starlight_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanElite(_Keyboard):
    USB_PID = 0x0228
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect', 'set_starlight_single_effect', 'set_starlight_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanMini(_Keyboard):
    USB_PID = 0x0257
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 14]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanMiniAnalog(_Keyboard):
    USB_PID = 0x0282
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 14]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanTournamentEdition(_Keyboard):
    USB_PID = 0x0243
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 18]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanV2(_Keyboard):
    USB_PID = 0x026C
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect', 'set_starlight_single_effect', 'set_starlight_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanV2Analog(_Keyboard):
    USB_PID = 0x0266
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_breath_random_effect', 'set_breath_single_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanV2TKL(_Keyboard):
    USB_PID = 0x026B
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 18]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanV3Pro(_Keyboard):
    USB_PID = 0x02A6
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanV3ProTKL(_Keyboard):
    USB_PID = 0x02A7
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 18]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerHuntsmanV3ProMini(_Keyboard):
    USB_PID = 0x02A8
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 14]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


# ── Ornata ────────────────────────────────────────────────────────────────────

class RazerOrnataChroma(_KeyboardStandard):
    USB_PID = 0x021E
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerOrnataChromaV2(_Keyboard):
    USB_PID = 0x025D
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect',
               'set_custom_effect', 'set_key_row']


class RazerOrnataV3(_Keyboard):
    USB_PID = 0x0294
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerOrnataV3X(_Keyboard):
    USB_PID = 0x029F
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect',
               'set_breath_random_effect', 'set_breath_single_effect']


class RazerOrnataV3TKL(_Keyboard):
    USB_PID = 0x02A3
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 18]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect',
               'set_custom_effect', 'set_key_row']


# ── DeathStalker ──────────────────────────────────────────────────────────────

class RazerDeathStalkerV2(_Keyboard):
    USB_PID = 0x0295
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_starlight_random_effect',
               'set_custom_effect', 'set_key_row']


class RazerDeathStalkerV2ProTKL(_Keyboard):
    USB_PID = 0x0298
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 18]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row',
               'get_battery', 'is_charging']


class RazerDeathStalkerV2Pro(_Keyboard):
    USB_PID = 0x0296
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row',
               'get_battery', 'is_charging']


# ── Cynosa ────────────────────────────────────────────────────────────────────

class RazerCynosaChromaV2(_Keyboard):
    USB_PID = 0x022A
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 22]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_reactive_effect',
               'set_breath_random_effect', 'set_breath_single_effect', 'set_breath_dual_effect',
               'set_custom_effect', 'set_key_row']


class RazerCynosaLite(_Keyboard):
    USB_PID = 0x023F
    HAS_MATRIX = False
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_breath_random_effect', 'set_breath_single_effect']


# ── Blade laptops (keyboard zone only) ───────────────────────────────────────

class RazerBladeAdvanced2019(_Keyboard):
    USB_PID = 0x023A
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 16]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_breath_random_effect', 'set_breath_single_effect',
               'set_custom_effect', 'set_key_row']


class RazerBladeBase2019(_Keyboard):
    USB_PID = 0x0246
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 16]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_breath_random_effect', 'set_breath_single_effect',
               'set_custom_effect', 'set_key_row']


class RazerBlade15Advanced2021(_Keyboard):
    USB_PID = 0x026D
    HAS_MATRIX = True
    MATRIX_DIMS = [6, 16]
    METHODS = ['get_firmware_version', 'get_serial', 'get_brightness', 'set_brightness',
               'set_static_effect', 'set_spectrum_effect', 'set_none_effect',
               'set_wave_effect', 'set_breath_random_effect', 'set_breath_single_effect',
               'set_custom_effect', 'set_key_row']

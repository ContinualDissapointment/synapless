"""
Mouse device definitions — mirrors upstream openrazer daemon/hardware/mouse.py.
"""

from .device_base import RazerDevice
from ..hid_layer.protocol import LOGO_LED, SCROLL_WHEEL_LED, LEFT_SIDE_LED, RIGHT_SIDE_LED


class _Mouse(RazerDevice):
    DEVICE_TYPE = "mouse"
    USE_EXTENDED_EFFECTS = True
    LOGO_LED_ID = LOGO_LED
    SCROLL_LED_ID = SCROLL_WHEEL_LED


_LOGO_METHODS = [
    'set_logo_static', 'set_logo_spectrum', 'set_logo_none', 'set_logo_reactive',
    'set_logo_breath_random', 'set_logo_breath_single', 'set_logo_breath_dual',
]
_SCROLL_METHODS = [
    'set_scroll_static', 'set_scroll_spectrum', 'set_scroll_none', 'set_scroll_reactive',
    'set_scroll_breath_random', 'set_scroll_breath_single', 'set_scroll_breath_dual',
]
_LEFT_METHODS = [
    'set_left_static', 'set_left_spectrum', 'set_left_none', 'set_left_reactive',
    'set_left_breath_random', 'set_left_breath_single', 'set_left_breath_dual',
]
_RIGHT_METHODS = [
    'set_right_static', 'set_right_spectrum', 'set_right_none', 'set_right_reactive',
    'set_right_breath_random', 'set_right_breath_single', 'set_right_breath_dual',
]
_BASE_MOUSE_METHODS = ['get_firmware_version', 'get_serial', 'max_dpi',
                       'get_dpi_xy', 'set_dpi_xy', 'get_poll_rate', 'set_poll_rate']
_BATTERY_METHODS = ['get_battery', 'is_charging']


class _MouseZones(_Mouse):
    """
    Mixin that routes zone-specific REST calls to the correct LED ID.
    The device_base.py set_static_effect etc. accept a zone= kwarg;
    these helpers make the zone explicit so the REST API can use named routes.
    """

    def set_logo_static(self, r, g, b):
        return self.set_static_effect(r, g, b, zone="logo")

    def set_logo_spectrum(self):
        return self.set_spectrum_effect(zone="logo")

    def set_logo_none(self):
        return self.set_none_effect(zone="logo")

    def set_logo_reactive(self, speed, r, g, b):
        return self.set_reactive_effect(speed, r, g, b, zone="logo")

    def set_logo_breath_random(self):
        return self.set_breath_random_effect(zone="logo")

    def set_logo_breath_single(self, r, g, b):
        return self.set_breath_single_effect(r, g, b, zone="logo")

    def set_logo_breath_dual(self, r1, g1, b1, r2, g2, b2):
        return self.set_breath_dual_effect(r1, g1, b1, r2, g2, b2, zone="logo")

    def set_scroll_static(self, r, g, b):
        return self.set_static_effect(r, g, b, zone="scroll")

    def set_scroll_spectrum(self):
        return self.set_spectrum_effect(zone="scroll")

    def set_scroll_none(self):
        return self.set_none_effect(zone="scroll")

    def set_scroll_reactive(self, speed, r, g, b):
        return self.set_reactive_effect(speed, r, g, b, zone="scroll")

    def set_scroll_breath_random(self):
        return self.set_breath_random_effect(zone="scroll")

    def set_scroll_breath_single(self, r, g, b):
        return self.set_breath_single_effect(r, g, b, zone="scroll")

    def set_scroll_breath_dual(self, r1, g1, b1, r2, g2, b2):
        return self.set_breath_dual_effect(r1, g1, b1, r2, g2, b2, zone="scroll")


class _MouseWithSides(_MouseZones):
    """Mouse with left/right RGB side strips."""

    LEFT_SIDE_LED_ID = LEFT_SIDE_LED
    RIGHT_SIDE_LED_ID = RIGHT_SIDE_LED

    def set_left_static(self, r, g, b):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_static(self.LEFT_SIDE_LED_ID, (r, g, b)))

    def set_left_spectrum(self):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_spectrum(self.LEFT_SIDE_LED_ID))

    def set_left_none(self):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_none(self.LEFT_SIDE_LED_ID))

    def set_left_reactive(self, speed, r, g, b):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_reactive(self.LEFT_SIDE_LED_ID, speed, (r, g, b)))

    def set_left_breath_random(self):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_breathing_random(self.LEFT_SIDE_LED_ID))

    def set_left_breath_single(self, r, g, b):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_breathing_single(self.LEFT_SIDE_LED_ID, (r, g, b)))

    def set_left_breath_dual(self, r1, g1, b1, r2, g2, b2):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_breathing_dual(self.LEFT_SIDE_LED_ID, (r1, g1, b1), (r2, g2, b2)))

    def set_right_static(self, r, g, b):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_static(self.RIGHT_SIDE_LED_ID, (r, g, b)))

    def set_right_spectrum(self):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_spectrum(self.RIGHT_SIDE_LED_ID))

    def set_right_none(self):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_none(self.RIGHT_SIDE_LED_ID))

    def set_right_reactive(self, speed, r, g, b):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_reactive(self.RIGHT_SIDE_LED_ID, speed, (r, g, b)))

    def set_right_breath_random(self):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_breathing_random(self.RIGHT_SIDE_LED_ID))

    def set_right_breath_single(self, r, g, b):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_breathing_single(self.RIGHT_SIDE_LED_ID, (r, g, b)))

    def set_right_breath_dual(self, r1, g1, b1, r2, g2, b2):
        from ..hid_layer import effects as fx
        return self._send_effect(fx.ext_breathing_dual(self.RIGHT_SIDE_LED_ID, (r1, g1, b1), (r2, g2, b2)))


# ── DeathAdder ────────────────────────────────────────────────────────────────

class RazerDeathAdderV2(_MouseZones):
    USB_PID = 0x0084
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 20000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + [
        'get_logo_brightness', 'set_logo_brightness',
        'get_scroll_brightness', 'set_scroll_brightness',
        'set_custom_effect', 'set_key_row',
    ]


class RazerDeathAdderV2Mini(_MouseZones):
    USB_PID = 0x008C
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 8500
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + ['set_custom_effect', 'set_key_row']


class RazerDeathAdderV2Pro(_MouseZones):
    USB_PID = 0x007C
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 20000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + _BATTERY_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]


class RazerDeathAdderV2ProWireless(RazerDeathAdderV2Pro):
    USB_PID = 0x007D


class RazerDeathAdderV3(_MouseZones):
    USB_PID = 0x00B3
    HAS_MATRIX = False
    DPI_MAX = 30000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS


class RazerDeathAdderV3Pro(_MouseZones):
    USB_PID = 0x00B6
    HAS_MATRIX = False
    DPI_MAX = 30000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _BATTERY_METHODS


class RazerDeathAdderV3HyperSpeed(_Mouse):
    USB_PID = 0x00B4
    DPI_MAX = 26000
    METHODS = _BASE_MOUSE_METHODS + _BATTERY_METHODS


class RazerDeathAdderEssential(_MouseZones):
    USB_PID = 0x006E
    DPI_MAX = 6400
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS


class RazerDeathAdderEssentialV2(_MouseZones):
    USB_PID = 0x0098
    DPI_MAX = 6400
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS


# ── Viper ─────────────────────────────────────────────────────────────────────

class RazerViper(_MouseZones):
    USB_PID = 0x0078
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 16000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + ['set_custom_effect', 'set_key_row']


class RazerViperMini(_MouseZones):
    USB_PID = 0x008A
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 8500
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + ['set_custom_effect', 'set_key_row']


class RazerViperUltimateWired(_MouseZones):
    USB_PID = 0x007A
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 20000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + _BATTERY_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]


class RazerViperUltimateWireless(RazerViperUltimateWired):
    USB_PID = 0x007B


class RazerViper8KHz(_MouseZones):
    USB_PID = 0x0091
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 20000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + ['set_custom_effect', 'set_key_row']


class RazerViperV2Pro(_MouseZones):
    USB_PID = 0x00A5
    HAS_MATRIX = False
    DPI_MAX = 30000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _BATTERY_METHODS


class RazerViperV2ProWireless(RazerViperV2Pro):
    USB_PID = 0x00A6


class RazerViperV3(_MouseZones):
    USB_PID = 0x00B1
    HAS_MATRIX = False
    DPI_MAX = 35000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS


class RazerViperV3HyperSpeed(_Mouse):
    USB_PID = 0x00B2
    DPI_MAX = 30000
    METHODS = _BASE_MOUSE_METHODS + _BATTERY_METHODS


class RazerViperV3Pro(_MouseZones):
    USB_PID = 0x00AF
    HAS_MATRIX = False
    DPI_MAX = 35000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _BATTERY_METHODS


class RazerViperV3ProWireless(RazerViperV3Pro):
    USB_PID = 0x00B0


# ── Basilisk ──────────────────────────────────────────────────────────────────

class RazerBasiliskV2(_MouseZones):
    USB_PID = 0x0085
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 20000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]


class RazerBasiliskV3(_MouseZones):
    USB_PID = 0x0099
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 11]
    DPI_MAX = 26000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]


class RazerBasiliskV3Pro(_MouseWithSides):
    USB_PID = 0x00AA
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 13]
    DPI_MAX = 30000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + _LEFT_METHODS + _RIGHT_METHODS + _BATTERY_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]


class RazerBasiliskV3ProWireless(RazerBasiliskV3Pro):
    USB_PID = 0x00AB


class RazerBasiliskXHyperSpeed(_Mouse):
    USB_PID = 0x0083
    DPI_MAX = 16000
    METHODS = _BASE_MOUSE_METHODS + _BATTERY_METHODS


class RazerBasiliskUltimateWired(_MouseZones):
    USB_PID = 0x0086
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 20000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + _BATTERY_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]


class RazerBasiliskUltimateReceiver(RazerBasiliskUltimateWired):
    USB_PID = 0x0088


# ── Naga ──────────────────────────────────────────────────────────────────────

class RazerNagaX(_MouseZones):
    USB_PID = 0x0096
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 2]
    DPI_MAX = 18000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]


class RazerNagaTrinity(_MouseZones):
    USB_PID = 0x0067
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 3]
    DPI_MAX = 16000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]


class RazerNagaV2Pro(_MouseWithSides):
    USB_PID = 0x00A7
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 30000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _SCROLL_METHODS + _LEFT_METHODS + _BATTERY_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]


# ── Orochi ────────────────────────────────────────────────────────────────────

class RazerOrochiV2(_Mouse):
    USB_PID = 0x008F
    DPI_MAX = 18000
    METHODS = _BASE_MOUSE_METHODS + _BATTERY_METHODS + _LOGO_METHODS


# ── Cobra ─────────────────────────────────────────────────────────────────────

class RazerCobra(_MouseZones):
    USB_PID = 0x00A3
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 8500
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + ['set_custom_effect', 'set_key_row']


class RazerCobraPro(_MouseWithSides):
    USB_PID = 0x00A4
    HAS_MATRIX = True
    MATRIX_DIMS = [1, 1]
    DPI_MAX = 30000
    METHODS = _BASE_MOUSE_METHODS + _LOGO_METHODS + _LEFT_METHODS + _RIGHT_METHODS + [
        'set_custom_effect', 'set_key_row',
    ]

"""
FastAPI REST server.

All routes are prefixed with /api/v1.
The server binds to 127.0.0.1:8083 (localhost only) so no firewall rules needed.
"""

import logging
import os
from typing import Annotated, Optional

from fastapi import FastAPI, HTTPException, Path, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

from .device_manager import DeviceManager
from .macro_manager import MacroManager

log = logging.getLogger(__name__)

PORT = 8083
HOST = "127.0.0.1"

app = FastAPI(title="openrazer-win", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Injected at startup by daemon.py
_manager: Optional[DeviceManager] = None
_macros: Optional[MacroManager] = None


def set_manager(manager: DeviceManager) -> None:
    global _manager
    _manager = manager


def set_macro_manager(manager: MacroManager) -> None:
    global _macros
    _macros = manager


def _get_device(serial: str):
    if _manager is None:
        raise HTTPException(503, "Service not ready")
    device = _manager.get_device(serial)
    if device is None:
        raise HTTPException(404, f"Device '{serial}' not found")
    return device


# ── Models ────────────────────────────────────────────────────────────────────

class RGB(BaseModel):
    r: int = Field(ge=0, le=255)
    g: int = Field(ge=0, le=255)
    b: int = Field(ge=0, le=255)


class RGBDual(BaseModel):
    r1: int = Field(ge=0, le=255)
    g1: int = Field(ge=0, le=255)
    b1: int = Field(ge=0, le=255)
    r2: int = Field(ge=0, le=255)
    g2: int = Field(ge=0, le=255)
    b2: int = Field(ge=0, le=255)


class SpeedRGB(BaseModel):
    speed: int = Field(ge=1, le=4, default=2)
    r: int = Field(ge=0, le=255)
    g: int = Field(ge=0, le=255)
    b: int = Field(ge=0, le=255)


class SpeedRGBDual(BaseModel):
    speed: int = Field(ge=1, le=3, default=2)
    r1: int = Field(ge=0, le=255)
    g1: int = Field(ge=0, le=255)
    b1: int = Field(ge=0, le=255)
    r2: int = Field(ge=0, le=255)
    g2: int = Field(ge=0, le=255)
    b2: int = Field(ge=0, le=255)


class WaveParams(BaseModel):
    direction: int = Field(ge=1, le=2, default=1)


class DPIParams(BaseModel):
    dpi_x: int = Field(ge=100, le=45000)
    dpi_y: Optional[int] = None


class PollRateParams(BaseModel):
    hz: int

    @field_validator("hz")
    @classmethod
    def valid_hz(cls, v):
        if v not in (125, 250, 500, 1000):
            raise ValueError("hz must be 125, 250, 500, or 1000")
        return v


class BrightnessParams(BaseModel):
    brightness: float = Field(ge=0, le=100)


class KeyRowParams(BaseModel):
    row: int = Field(ge=0)
    start_col: int = Field(ge=0)
    colors: list[list[int]]  # list of [r, g, b]

    @field_validator("colors")
    @classmethod
    def validate_colors(cls, v):
        for c in v:
            if len(c) != 3 or not all(0 <= x <= 255 for x in c):
                raise ValueError("Each color must be [r, g, b] with values 0–255")
        return v


# ── Devices ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/devices")
def list_devices():
    if _manager is None:
        raise HTTPException(503, "Service not ready")
    return {"devices": _manager.list_devices()}


@app.get("/api/v1/devices/{serial}")
def get_device(serial: str):
    device = _get_device(serial)
    return device.get_device_info()


# ── Brightness ────────────────────────────────────────────────────────────────

@app.get("/api/v1/devices/{serial}/brightness")
def get_brightness(serial: str):
    return {"brightness": _get_device(serial).get_brightness()}


@app.post("/api/v1/devices/{serial}/brightness")
def set_brightness(serial: str, params: BrightnessParams):
    _get_device(serial).set_brightness(params.brightness)
    return {"ok": True}


# ── Effects ───────────────────────────────────────────────────────────────────

def _zone_route(zone: str):
    """Return a prefix segment for zone-specific routes, or empty string for backlight."""
    return f"/{zone}" if zone != "backlight" else ""


def _register_lighting_routes(zone: str = "backlight") -> None:
    zp = _zone_route(zone)

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/none", tags=["lighting"])
    def set_none(serial: str):
        _get_device(serial).set_none_effect(zone=zone)
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/spectrum", tags=["lighting"])
    def set_spectrum(serial: str):
        _get_device(serial).set_spectrum_effect(zone=zone)
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/static", tags=["lighting"])
    def set_static(serial: str, rgb: RGB):
        _get_device(serial).set_static_effect(rgb.r, rgb.g, rgb.b, zone=zone)
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/wave", tags=["lighting"])
    def set_wave(serial: str, params: WaveParams):
        _get_device(serial).set_wave_effect(direction=params.direction, zone=zone)
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/reactive", tags=["lighting"])
    def set_reactive(serial: str, params: SpeedRGB):
        _get_device(serial).set_reactive_effect(params.speed, params.r, params.g, params.b, zone=zone)
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/breath/random", tags=["lighting"])
    def set_breath_random(serial: str):
        _get_device(serial).set_breath_random_effect(zone=zone)
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/breath/single", tags=["lighting"])
    def set_breath_single(serial: str, rgb: RGB):
        _get_device(serial).set_breath_single_effect(rgb.r, rgb.g, rgb.b, zone=zone)
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/breath/dual", tags=["lighting"])
    def set_breath_dual(serial: str, params: RGBDual):
        _get_device(serial).set_breath_dual_effect(
            params.r1, params.g1, params.b1, params.r2, params.g2, params.b2, zone=zone
        )
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/starlight/random", tags=["lighting"])
    def set_starlight_random(serial: str, speed: int = 1):
        _get_device(serial).set_starlight_random_effect(speed=speed, zone=zone)
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/starlight/single", tags=["lighting"])
    def set_starlight_single(serial: str, params: SpeedRGB):
        _get_device(serial).set_starlight_single_effect(params.speed, params.r, params.g, params.b, zone=zone)
        return {"ok": True}

    @app.post(f"/api/v1/devices/{{serial}}/lighting{zp}/starlight/dual", tags=["lighting"])
    def set_starlight_dual(serial: str, params: SpeedRGBDual):
        _get_device(serial).set_starlight_dual_effect(
            params.speed, params.r1, params.g1, params.b1, params.r2, params.g2, params.b2, zone=zone
        )
        return {"ok": True}


# Register routes for all zones
for _zone in ("backlight", "logo", "scroll"):
    _register_lighting_routes(_zone)


# ── Custom matrix ─────────────────────────────────────────────────────────────

@app.post("/api/v1/devices/{serial}/lighting/custom", tags=["lighting"])
def set_custom_effect(serial: str):
    _get_device(serial).set_custom_effect()
    return {"ok": True}


@app.post("/api/v1/devices/{serial}/lighting/keyrow", tags=["lighting"])
def set_key_row(serial: str, params: KeyRowParams):
    flat = bytes(c for rgb in params.colors for c in rgb)
    stop_col = params.start_col + len(params.colors) - 1
    _get_device(serial).set_key_row(params.row, params.start_col, stop_col, flat)
    return {"ok": True}


# ── DPI ───────────────────────────────────────────────────────────────────────

@app.get("/api/v1/devices/{serial}/dpi", tags=["mouse"])
def get_dpi(serial: str):
    device = _get_device(serial)
    dpi_x, dpi_y = device.get_dpi_xy()
    return {"dpi_x": dpi_x, "dpi_y": dpi_y, "max_dpi": device.max_dpi()}


@app.post("/api/v1/devices/{serial}/dpi", tags=["mouse"])
def set_dpi(serial: str, params: DPIParams):
    dpi_y = params.dpi_y if params.dpi_y is not None else params.dpi_x
    _get_device(serial).set_dpi_xy(params.dpi_x, dpi_y)
    return {"ok": True}


# ── Polling rate ──────────────────────────────────────────────────────────────

@app.get("/api/v1/devices/{serial}/polling", tags=["mouse"])
def get_polling(serial: str):
    return {"hz": _get_device(serial).get_poll_rate()}


@app.post("/api/v1/devices/{serial}/polling", tags=["mouse"])
def set_polling(serial: str, params: PollRateParams):
    _get_device(serial).set_poll_rate(params.hz)
    return {"ok": True}


# ── Battery ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/devices/{serial}/battery", tags=["battery"])
def get_battery(serial: str):
    device = _get_device(serial)
    return {
        "battery": device.get_battery(),
        "charging": device.is_charging(),
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
def health():
    count = len(_manager.list_devices()) if _manager else 0
    return {"status": "ok", "devices": count}


@app.get("/api/v1/debug/hid")
def debug_hid():
    """Return raw hid.enumerate output for diagnostics."""
    import sys, os
    try:
        import hid
        all_devs = hid.enumerate(0, 0)
        razer = [d for d in all_devs if d.get("vendor_id") == 0x1532]
        return {
            "hid_version": getattr(hid, "__version__", "unknown"),
            "frozen": getattr(sys, "frozen", False),
            "meipass": getattr(sys, "_MEIPASS", None),
            "total_hid_devices": len(all_devs),
            "razer_devices": razer,
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


# ── Macros ───────────────────────────────────────────────────────────────────

class MacroConfig(BaseModel):
    sequence: str
    mode: str
    interval_ms: int = Field(default=50, ge=10, le=5000)
    record_timing: bool = False

    @field_validator('mode')
    @classmethod
    def valid_mode(cls, v):
        if v not in ('once', 'hold', 'toggle', 'start_stop'):
            raise ValueError("mode must be once, hold, toggle, or start_stop")
        return v


@app.get("/api/v1/macros")
def list_macros():
    return {"macros": _macros.get_all() if _macros else {}}


@app.put("/api/v1/macros/{key}")
def set_macro(key: str, config: MacroConfig):
    if _macros is None:
        raise HTTPException(503, "Macro manager not ready")
    _macros.set_macro(key, config.sequence, config.mode, config.interval_ms, config.record_timing)
    return {"ok": True}


@app.delete("/api/v1/macros/{key}")
def delete_macro(key: str):
    if _macros is None:
        raise HTTPException(503, "Macro manager not ready")
    _macros.delete_macro(key)
    return {"ok": True}


# ── GUI ───────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def gui():
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

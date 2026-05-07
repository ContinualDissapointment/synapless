"""
openrazer-win Python client library.

Mirrors the interface of the upstream openrazer pylib where practical so
existing scripts can be adapted with minimal changes.

Requires: pip install httpx
"""

from __future__ import annotations

import httpx

DEFAULT_URL = "http://127.0.0.1:8083"


class OpenRazerClient:
    """Top-level client — mirrors openrazer.client.DeviceManager."""

    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 5.0):
        self._http = httpx.Client(base_url=base_url, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def get_devices(self) -> list["RazerDevice"]:
        resp = self._http.get("/api/v1/devices")
        resp.raise_for_status()
        return [RazerDevice(d, self._http) for d in resp.json()["devices"]]

    def get_device(self, serial: str) -> "RazerDevice":
        resp = self._http.get(f"/api/v1/devices/{serial}")
        resp.raise_for_status()
        return RazerDevice(resp.json(), self._http)

    def is_connected(self) -> bool:
        try:
            self._http.get("/api/v1/health").raise_for_status()
            return True
        except Exception:
            return False


class RazerDevice:
    """Represents a single connected Razer device."""

    def __init__(self, info: dict, http: httpx.Client):
        self._info = info
        self._http = http
        self.serial: str = info["serial"]
        self.name: str = info["product"]
        self.type: str = info["type"]
        self.firmware_version: str = info["firmware"]
        self.has_matrix: bool = info.get("has_matrix", False)
        self.matrix_dims: list | None = info.get("matrix_dims")
        self.max_dpi: int | None = info.get("dpi_max")
        self._methods: list[str] = info.get("methods", [])

    def has_fx(self, method: str) -> bool:
        return method in self._methods

    def _post(self, path: str, json: dict | None = None) -> dict:
        resp = self._http.post(f"/api/v1/devices/{self.serial}/{path}", json=json or {})
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str) -> dict:
        resp = self._http.get(f"/api/v1/devices/{self.serial}/{path}")
        resp.raise_for_status()
        return resp.json()

    # ── Brightness ────────────────────────────────────────────────────────────

    @property
    def brightness(self) -> float:
        return self._get("brightness")["brightness"]

    @brightness.setter
    def brightness(self, value: float) -> None:
        self._post("brightness", {"brightness": float(value)})

    # ── Lighting effects ──────────────────────────────────────────────────────

    def set_static(self, r: int, g: int, b: int, zone: str = "backlight") -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/static", {"r": r, "g": g, "b": b})

    def set_none(self, zone: str = "backlight") -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/none")

    def set_spectrum(self, zone: str = "backlight") -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/spectrum")

    def set_wave(self, direction: int = 1, zone: str = "backlight") -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/wave", {"direction": direction})

    def set_reactive(self, speed: int, r: int, g: int, b: int, zone: str = "backlight") -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/reactive", {"speed": speed, "r": r, "g": g, "b": b})

    def set_breath_random(self, zone: str = "backlight") -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/breath/random")

    def set_breath_single(self, r: int, g: int, b: int, zone: str = "backlight") -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/breath/single", {"r": r, "g": g, "b": b})

    def set_breath_dual(
        self, r1: int, g1: int, b1: int, r2: int, g2: int, b2: int, zone: str = "backlight"
    ) -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/breath/dual",
                   {"r1": r1, "g1": g1, "b1": b1, "r2": r2, "g2": g2, "b2": b2})

    def set_starlight_random(self, speed: int = 1, zone: str = "backlight") -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/starlight/random", {"speed": speed})

    def set_starlight_single(self, speed: int, r: int, g: int, b: int, zone: str = "backlight") -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/starlight/single", {"speed": speed, "r": r, "g": g, "b": b})

    def set_starlight_dual(
        self, speed: int, r1: int, g1: int, b1: int, r2: int, g2: int, b2: int, zone: str = "backlight"
    ) -> None:
        zp = f"/{zone}" if zone != "backlight" else ""
        self._post(f"lighting{zp}/starlight/dual",
                   {"speed": speed, "r1": r1, "g1": g1, "b1": b1, "r2": r2, "g2": g2, "b2": b2})

    # ── Custom per-key RGB ────────────────────────────────────────────────────

    def set_custom_effect(self) -> None:
        self._post("lighting/custom")

    def set_key_row(self, row: int, start_col: int, colors: list[tuple[int, int, int]]) -> None:
        self._post("lighting/keyrow", {
            "row": row,
            "start_col": start_col,
            "colors": [list(c) for c in colors],
        })

    # ── Mouse: DPI ────────────────────────────────────────────────────────────

    def get_dpi(self) -> tuple[int, int]:
        d = self._get("dpi")
        return d["dpi_x"], d["dpi_y"]

    def set_dpi(self, dpi_x: int, dpi_y: int | None = None) -> None:
        self._post("dpi", {"dpi_x": dpi_x, "dpi_y": dpi_y if dpi_y is not None else dpi_x})

    # ── Mouse: polling rate ───────────────────────────────────────────────────

    def get_poll_rate(self) -> int:
        return self._get("polling")["hz"]

    def set_poll_rate(self, hz: int) -> None:
        self._post("polling", {"hz": hz})

    # ── Battery ───────────────────────────────────────────────────────────────

    def get_battery(self) -> float:
        return self._get("battery")["battery"]

    def is_charging(self) -> bool:
        return self._get("battery")["charging"]

    def __repr__(self) -> str:
        return f"<RazerDevice {self.name!r} serial={self.serial!r}>"

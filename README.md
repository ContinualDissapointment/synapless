# synapless

Control your Razer peripherals on Windows without installing Razer Synapse.

Built on top of the open USB protocol documented by the [OpenRazer](https://github.com/openrazer/openrazer) project (Linux).
Runs as a Windows Service and exposes a local REST API — no cloud account, no telemetry, no 400 MB Electron app phoning home.

---

## Pre-built release

Download `synapless.exe` from the [Releases](https://github.com/ContinualDissapointment/synapless/releases) page.

> **Windows Defender / SmartScreen warning** — the EXE is unsigned (code signing
> certificates cost ~$300/yr). Click **"More info" → "Run anyway"** to proceed.
> The source is fully open; build it yourself if you prefer (see below).

---

## Requirements

- Windows 10 or 11 (x64)
- Run as **Administrator** (required for HID feature reports and driver install)
- Python 3.10+ (only if running from source)

---

## Quick start (pre-built EXE)

```powershell
# Run PowerShell as Administrator

.\synapless.exe debug          # foreground, Ctrl+C to stop
# browse http://127.0.0.1:8083/docs
```

To install as a Windows Service that starts automatically:

```powershell
.\synapless.exe install
.\synapless.exe start
.\synapless.exe stop
.\synapless.exe remove
```

Logs: `C:\ProgramData\openrazer-win\logs\service.log`

---

## Quick start (from source)

```powershell
# Python 3.10+, run PowerShell as Administrator

git clone https://github.com/ContinualDissapointment/synapless
cd synapless
pip install -e ".[client]"

synapless debug          # Ctrl+C to stop
```

---

## Macro keys (Tartarus Pro)

Macros require a kernel filter driver (`kbfiltr.sys`) that intercepts keypresses at the driver level before they reach any application. This gives clean per-device suppression with no ghost typing.

### One-time setup (requires reboot)

**Step 1 — Enable test-signing mode** (driver is self-signed; a commercial EV cert costs ~$300/yr):

```powershell
# Run as Administrator
bcdedit /set testsigning on
# Reboot
```

A small "Test Mode" watermark will appear in the bottom-right corner of the desktop. This is cosmetic only.

**Step 2 — Install the filter driver:**

```powershell
# Run as Administrator after reboot
.\synapless.exe driver install    # or: python -m service.driver_install install
```

**Step 3 — Replug the Tartarus Pro** so Windows re-enumerates it with the filter attached.

**Step 4 — Start the service** and configure macros via the web UI at `http://127.0.0.1:8083`.

### Uninstall driver

```powershell
.\synapless.exe driver uninstall
bcdedit /set testsigning off
# Reboot
```

### Without the driver

Macros still work via a fallback hook (`WH_KEYBOARD_LL` + Raw Input). The fallback is slightly noisier: the very first keypress after a >1 s idle period also types the trigger key before the macro fires. Every subsequent press is clean.

---

## REST API

All routes under `/api/v1`. Interactive docs at `http://127.0.0.1:8083/docs`.

### Devices
```
GET  /api/v1/devices
GET  /api/v1/devices/{serial}
```

### Lighting
```
POST /api/v1/devices/{serial}/lighting/static      {"r":255,"g":0,"b":0}
POST /api/v1/devices/{serial}/lighting/none
POST /api/v1/devices/{serial}/lighting/spectrum
POST /api/v1/devices/{serial}/lighting/wave        {"direction":1}
POST /api/v1/devices/{serial}/lighting/reactive    {"speed":2,"r":255,"g":0,"b":0}
POST /api/v1/devices/{serial}/lighting/breath/random
POST /api/v1/devices/{serial}/lighting/breath/single  {"r":0,"g":255,"b":0}
POST /api/v1/devices/{serial}/lighting/breath/dual    {"r1":255,"g1":0,"b1":0,"r2":0,"g2":0,"b2":255}
POST /api/v1/devices/{serial}/lighting/starlight/random  {"speed":1}
POST /api/v1/devices/{serial}/lighting/starlight/single  {"speed":1,"r":255,"g":255,"b":255}
POST /api/v1/devices/{serial}/brightness           {"brightness": 80}
```

Mouse zones: swap `lighting/` for `lighting/logo/` or `lighting/scroll/`.

### Per-key RGB
```python
import httpx
serial = "YOUR_SERIAL"
base = f"http://127.0.0.1:8083/api/v1/devices/{serial}"

# Paint row 0 red
httpx.post(f"{base}/lighting/keyrow", json={
    "row": 0, "start_col": 0, "colors": [[255,0,0]] * 22
})
httpx.post(f"{base}/lighting/custom")
```

### Macros
```
GET    /api/v1/macros
PUT    /api/v1/macros/{key}   {"sequence":"ctrl+c","mode":"once"}
DELETE /api/v1/macros/{key}
```

Modes: `once`, `hold` (spam while held), `toggle`, `start_stop`.

### Mouse
```
GET  /api/v1/devices/{serial}/dpi
POST /api/v1/devices/{serial}/dpi        {"dpi_x":1600}
GET  /api/v1/devices/{serial}/polling
POST /api/v1/devices/{serial}/polling    {"hz":500}
GET  /api/v1/devices/{serial}/battery
```

---

## Python client

```python
from pylib.client import OpenRazerClient

with OpenRazerClient() as c:
    for dev in c.get_devices():
        print(dev.name, dev.serial)
        dev.set_static(0, 255, 128)
        dev.brightness = 75

    mouse = next(d for d in c.get_devices() if d.type == "mouse")
    mouse.set_dpi(1600)
    print(f"Battery: {mouse.get_battery():.1f}%  Charging: {mouse.is_charging()}")
```

---

## Build from source

```powershell
pip install pyinstaller
pyinstaller synapless.spec
# output: dist\synapless.exe
```

---

## Keeping device support current

```powershell
python scripts/sync_devices.py
```

Fetches the latest device tables from the OpenRazer repo and adapts them for Windows.

---

## Architecture

```
synapless/
├── driver/
│   └── kbfiltr/
│       └── kbfiltr.sys    Kernel filter driver — per-device macro suppression
├── service/
│   ├── hid_layer/
│   │   ├── protocol.py    90-byte Razer report structure
│   │   ├── effects.py     Lighting effect builders
│   │   └── transport.py   HIDAPI wrapper
│   ├── hardware/
│   │   ├── device_base.py All protocol methods
│   │   ├── keyboards.py   Keyboard PID table
│   │   └── mouse.py       Mouse PID table
│   ├── device_manager.py  Hot-plug detection
│   ├── macro_manager.py   Macro engine (kernel filter + hook fallback)
│   ├── kbfiltr_client.py  Usermode client for kbfiltr.sys
│   ├── driver_install.py  Driver install / uninstall CLI
│   ├── api.py             FastAPI REST server
│   └── daemon.py          Windows Service wrapper
├── pylib/
│   └── client.py          Python REST client
└── scripts/
    └── sync_devices.py    Sync device support from upstream
```

Lighting uses [HIDAPI](https://github.com/libusb/hidapi) to send feature reports directly — no kernel driver required. The kernel driver (`kbfiltr.sys`) is only needed for clean macro key suppression on the Tartarus Pro.

---

## Supported devices (65 total)

**Keyboards:** BlackWidow Chroma V2, V3, V3 Mini, V3 TKL, V3 Pro, V4, V4 Pro, V4 X — Huntsman (all variants through V3 Pro) — Ornata Chroma, V2, V3, V3 X, V3 TKL — DeathStalker V2/Pro/Pro TKL — Cynosa Chroma V2, Cynosa Lite — Blade 15/Advanced

**Mice:** DeathAdder V2/V2 Mini/V2 Pro/V3/V3 Pro/V3 HyperSpeed/Essential — Viper/Mini/Ultimate/8KHz/V2 Pro/V3/V3 HyperSpeed/V3 Pro — Basilisk V2/V3/V3 Pro/X HyperSpeed/Ultimate — Naga X/Trinity/V2 Pro — Orochi V2 — Cobra/Cobra Pro

**Keypads:** Tartarus Pro, Tartarus V2

---

## Troubleshooting

**Device not found** — run as Administrator.

**Macros: driver not loading** — check that test-signing is on (`bcdedit /enum | findstr testsigning`), that you rebooted after enabling it, and that the Tartarus was replugged after `driver install`. Check `service.log` for errors.

**Macros: "Test Mode" watermark won't go away** — run `bcdedit /set testsigning off` and reboot after uninstalling the driver.

**Effects don't apply** — some older devices use standard effect commands (class `0x03`) rather than extended (class `0x0F`). Set `USE_EXTENDED_EFFECTS = False` in the device class. Open an issue with your PID.

**New device not listed** — run `python scripts/sync_devices.py` or add a class to `service/hardware/keyboards.py` / `mouse.py`.

---

## Relationship to OpenRazer

This project ports the USB protocol documented in [OpenRazer](https://github.com/openrazer/openrazer)'s Linux kernel driver source to Python/Windows. Device class definitions are synced from upstream. Not a fork of [openrazer-win32](https://github.com/CalcProgrammer1/openrazer-win32).

## License

GPL-2.0-or-later, same as upstream OpenRazer.

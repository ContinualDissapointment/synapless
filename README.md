# synapless

> **⚠️ PROOF OF CONCEPT — UNTESTED ON REAL HARDWARE**
> This was built by reverse-engineering the [OpenRazer](https://github.com/openrazer/openrazer)
> source and porting the USB protocol to Python. It has not yet been run against a physical
> Razer device. Expect bugs. PRs welcome.

Control your Razer peripherals on Windows without installing Razer Synapse.

Built on top of the open USB protocol documented by the OpenRazer project (Linux).
Runs as a Windows Service and exposes a local REST API — no cloud account, no telemetry,
no 400 MB electron app phoning home.

---

## Quick start

```powershell
# Python 3.10+ required. Run PowerShell as Administrator.

git clone https://github.com/ContinualDissapointment/synapless
cd synapless
pip install -e ".[client]"

# Run in foreground (Ctrl+C to stop)
synapless debug
```

Browse to `http://127.0.0.1:8083/docs` for the interactive API.

---

## Install as a Windows Service

```powershell
# Run as Administrator
synapless install
synapless start
```

Logs: `C:\ProgramData\synapless\logs\service.log`

```powershell
synapless stop
synapless remove
```

---

## REST API

All routes under `/api/v1`. Full interactive docs at `http://127.0.0.1:8083/docs`.

### Devices
```
GET  /api/v1/devices
GET  /api/v1/devices/{serial}
```

### Lighting
```
POST /api/v1/devices/{serial}/brightness           {"brightness": 80}
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
```

Mouse zones: swap `lighting/` for `lighting/logo/` or `lighting/scroll/`.

### Per-key RGB
```python
import httpx
serial = "YOUR_SERIAL"
base = f"http://127.0.0.1:8083/api/v1/devices/{serial}"

# Paint row 0 red
httpx.post(f"{base}/lighting/keyrow", json={
    "row": 0, "start_col": 0,
    "colors": [[255,0,0]] * 22
})
httpx.post(f"{base}/lighting/custom")
```

### Mouse
```
GET  /api/v1/devices/{serial}/dpi        {"dpi_x":800,"dpi_y":800,"max_dpi":20000}
POST /api/v1/devices/{serial}/dpi        {"dpi_x":1600}
GET  /api/v1/devices/{serial}/polling    {"hz":1000}
POST /api/v1/devices/{serial}/polling    {"hz":500}
GET  /api/v1/devices/{serial}/battery    {"battery":87.5,"charging":false}
```

---

## Python client

```python
from pylib.client import OpenRazerClient

with OpenRazerClient() as c:
    for dev in c.get_devices():
        print(dev.name, dev.serial)
        dev.set_static(0, 255, 128)   # green
        dev.brightness = 75

    mouse = next(d for d in c.get_devices() if d.type == "mouse")
    mouse.set_dpi(1600)
    mouse.set_poll_rate(1000)
    print(f"Battery: {mouse.get_battery():.1f}%  Charging: {mouse.is_charging()}")
```

---

## Keeping device support current

When upstream OpenRazer adds a new device, pull it in:

```powershell
python scripts/sync_devices.py
```

This fetches the latest device tables from the OpenRazer repo and adapts them for Windows.

---

## Architecture

```
synapless/
├── service/
│   ├── hid_layer/
│   │   ├── protocol.py    90-byte Razer report structure (from razercommon.h/c)
│   │   ├── effects.py     Lighting effect builders (from razerchromacommon.c)
│   │   └── transport.py   HIDAPI wrapper — replaces Linux sysfs + kernel modules
│   ├── hardware/
│   │   ├── device_base.py All protocol methods live here
│   │   ├── keyboards.py   Keyboard PID table (synced from upstream openrazer)
│   │   └── mouse.py       Mouse PID table
│   ├── device_manager.py  Hot-plug detection — replaces udev
│   ├── api.py             FastAPI REST server — replaces D-Bus
│   └── daemon.py          Windows Service — replaces systemd
├── pylib/
│   └── client.py          Python REST client
└── scripts/
    └── sync_devices.py    Sync device support from upstream
```

**No kernel driver needed.** Razer devices expose a standard HID interface. Windows already has an HID class driver; this project uses [HIDAPI](https://github.com/libusb/hidapi) via the Python `hid` package to send feature reports from userspace. The service needs Administrator so Windows permits access to the HID feature report interface.

---

## Supported devices (65 total)

**Keyboards:** BlackWidow Chroma V2, V3, V3 Mini, V3 TKL, V3 Pro, V4, V4 Pro, V4 X — Huntsman (all variants through V3 Pro) — Ornata Chroma, V2, V3, V3 X, V3 TKL — DeathStalker V2/Pro/Pro TKL — Cynosa Chroma V2, Cynosa Lite — Blade 15/Advanced

**Mice:** DeathAdder V2/V2 Mini/V2 Pro/V3/V3 Pro/V3 HyperSpeed/Essential — Viper/Mini/Ultimate/8KHz/V2 Pro/V3/V3 HyperSpeed/V3 Pro — Basilisk V2/V3/V3 Pro/X HyperSpeed/Ultimate — Naga X/Trinity/V2 Pro — Orochi V2 — Cobra/Cobra Pro

---

## Troubleshooting

**Device not found** — run as Administrator.

**Effects don't apply** — some older devices use standard effect commands (class `0x03`) rather than extended (class `0x0F`). Set `USE_EXTENDED_EFFECTS = False` in the device class and try again. Open an issue with your PID.

**New device not listed** — run `python scripts/sync_devices.py` or add a class to `service/hardware/keyboards.py` / `mouse.py` following the existing pattern.

---

## Relationship to OpenRazer

This project ports the USB protocol documented in [OpenRazer](https://github.com/openrazer/openrazer)'s Linux kernel driver source to Python/Windows. Device class definitions are synced from upstream. This is not a fork of [openrazer-win32](https://github.com/CalcProgrammer1/openrazer-win32) — that project compiled the Linux C driver into a DLL using kernel API shims, which became impossible to maintain as the driver grew. This project reimplements the protocol cleanly.

## License

GPL-2.0-or-later, same as upstream OpenRazer.

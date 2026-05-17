# Tartarus Pro Analog Protocol — Research Notes

## Goal

Add analog key pressure support to [openrazer](https://github.com/openrazer/openrazer)
for the Razer Tartarus Pro (USB VID/PID `1532:0244`).

---

## What we know (captured on Windows via Wireshark + USBPcap)

### The device streams analog data natively — no enable command needed

Unlike what we expected, the Tartarus Pro does **not** require a special Synapse
command to enter "analog mode." It streams analog key pressure data continuously
from the moment it is plugged in, on a dedicated HID report.

### Report format

| Field       | Value |
|-------------|-------|
| Endpoint    | EP2 (interrupt IN) |
| Report ID   | `0x06` |
| Total size  | 24 bytes (1 byte report ID + 23 bytes data) |
| Rate        | ~1 ms polling (1000 Hz) |

### Observed data

All samples below are the 23 data bytes after the `0x06` report ID byte.

| State | Byte[0] | Byte[6] | Notes |
|-------|---------|---------|-------|
| Idle (no touch) | `00` | `91` | `91` (145) at byte[6] = thumbstick Y resting slightly off-center |
| Key pressed ~43% | `6e` (110) | `00` | First physical button pressed gradually |
| Key pressed ~44% | `70` (112) | `00` | Same button, slightly more pressure |

### Interpretation

- Each data byte likely corresponds to one key's analog pressure: `0x00` = not
  pressed, `0xFF` = fully pressed.
- The device has 21 individually addressable RGB zones / keys. The 23 data bytes
  probably cover 20 analog keys + thumbstick X + thumbstick Y (or similar).
- The thumbstick axes report non-zero at rest (resting position ≠ 0).

### What is NOT yet known (to be mapped on Linux)

- Which byte offset corresponds to which physical button.
- Exact max value for a fully-pressed key (probably `0xFF` but unconfirmed).
- Which byte(s) carry thumbstick X and Y.
- Whether the scroll wheel click is in this report or another.
- Whether the 8-way D-pad directions appear here or as standard HID hat switch.

---

## Why userspace can't read this on Windows

On Windows the Mouse HID collection (the one that owns report ID `0x06`) is
claimed exclusively by `mouhid.sys`. The `hid` Python library cannot open it.
On Linux this is a non-issue — `hidraw` gives direct byte-level access to every
HID collection without driver exclusivity.

---

## Linux testing plan (Proxmox USB passthrough)

### 1. Identify the right hidraw device

```bash
# Find all hidraw nodes for the Tartarus Pro
grep -r "1532" /sys/class/hidraw/*/device/uevent 2>/dev/null | grep -i "0244"

# Or list them all and grep for Razer
ls /sys/class/hidraw/
cat /sys/class/hidraw/hidraw0/device/uevent   # repeat for each
```

The device will have several hidraw nodes (one per HID collection). You want the
one whose report descriptor includes report ID `0x06`. Check with:

```bash
# Install hid-tools if needed: pip install hid-tools  OR  apt install python3-hid
python3 - << 'EOF'
import os, struct

for i in range(10):
    path = f"/dev/hidraw{i}"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        # HIDIOCGRDESCSIZE = 0x80044801, HIDIOCGRDESC = 0x90044802
        import fcntl, ctypes
        size_buf = ctypes.create_string_buffer(4)
        fcntl.ioctl(fd, 0x80044801, size_buf)
        size = struct.unpack_from("<I", size_buf)[0]
        desc_buf = ctypes.create_string_buffer(4 + 4096)
        struct.pack_into("<I", desc_buf, 0, size)
        fcntl.ioctl(fd, 0x90044802, desc_buf)
        desc = bytes(desc_buf[4:4+size])
        if b'\x06' in desc or 0x06 in desc:
            print(f"{path}: size={size}  descriptor hex={desc.hex()}")
        os.close(fd)
    except Exception as e:
        pass
EOF
```

Or use `hid-decode` from `hid-tools`:
```bash
for i in $(seq 0 9); do
    echo "=== hidraw$i ===" 
    hid-decode /sys/class/hidraw/hidraw$i/device/report_descriptor 2>/dev/null | head -30
done
```

### 2. Confirm analog data flows

```python
#!/usr/bin/env python3
"""Read raw HID reports from the Tartarus Pro on Linux."""
import os, sys, time

# Update this path after step 1 — probably hidraw2 or hidraw3
HIDRAW = "/dev/hidraw2"
TARGET_REPORT_ID = 0x06

fd = os.open(HIDRAW, os.O_RDONLY)
print(f"Reading from {HIDRAW} — press Tartarus keys at varying pressures")
print(f"Looking for report ID 0x{TARGET_REPORT_ID:02X}")
print()

prev = None
while True:
    data = os.read(fd, 64)
    if not data or data[0] != TARGET_REPORT_ID:
        continue
    payload = data[1:]
    if payload != prev:
        changed = []
        if prev:
            for i, (a, b) in enumerate(zip(prev, payload)):
                if a != b:
                    changed.append(f"byte[{i}]: {a:3d}→{b:3d} ({b-a:+d})")
        print(f"  {'  '.join(changed) or 'initial'}")
        print(f"  full: {payload.hex(' ')}")
        prev = payload
    time.sleep(0.01)
```

### 3. Map byte offset → physical key

Press each physical Tartarus button one at a time, fully (hold for ~1 second),
then release. Record which `byte[N]` changes. Build this table:

| Physical key | byte offset | Notes |
|---|---|---|
| Button 1 (top-left) | ? | |
| Button 2 | ? | |
| ... | | |
| Scroll wheel | ? | Maybe in a different report |
| Thumbstick X | ? | Non-zero at rest |
| Thumbstick Y | ? | Non-zero at rest (saw `0x91` on Windows) |
| D-pad Up | ? | May be HID hat switch in different report |

The Tartarus Pro key layout (from top-left, row by row):
```
[1] [2] [3] [4] [5]
[6] [7] [8] [9] [10]
[11][12][13][14]
[15][16][17]  [18]  ← 18 = mode switch key
[↑] [D-pad]  [thumbstick]
[scroll wheel]
```
(approximate — confirm by feel during testing)

### 4. Check the report descriptor

Once you find the right hidraw, dump and decode the report descriptor:
```bash
python3 -c "
import sys
with open('/sys/class/hidraw/hidrawX/device/report_descriptor', 'rb') as f:
    data = f.read()
print(data.hex(' '))
"
```

This will show us the HID usage declarations for each byte in report ID 6,
confirming the thumbstick axes, hat switch, and key usages.

---

## openrazer implementation plan

### Files to create/modify

```
openrazer/
├── driver/
│   ├── razertartaruspro_driver.c   # existing — add analog read handler
│   └── razercommon.h               # may need new ioctl or sysfs attr
└── daemon/
    └── openrazer_daemon/
        └── hardware/
            └── keyboards.py        # RazerTartarusPro class — add analog method
```

### Kernel driver side

The driver already handles the standard HID keyboard interface. We need to add:

1. **Open the hidraw device** for the collection that owns report ID `0x06`
   (this is the interface with `U=0x0000` or similar non-keyboard usage).
2. **Background kthread** that calls `hid_hw_raw_request()` or reads from
   the interrupt IN endpoint to get report-6 data.
3. **Expose via sysfs** as a new attribute, e.g.
   `/sys/bus/hid/devices/.../analog_keys` — returns a binary blob of 21 bytes
   (one per key, current pressure 0–255).
4. Alternatively expose via **uinput** as ABS_ axes so it looks like a joystick
   to userspace without any daemon changes.

### Daemon / D-Bus side

Add a new D-Bus property on the keypad interface:
```python
@dbus.service.method(...)
def getAnalogKeys(self):
    """Returns list of 21 uint8 values, one per key, 0=up 255=fully pressed."""
```

### Minimum viable PR

The smallest useful PR is a **read-only sysfs attribute** that exposes the raw
23-byte analog report, letting userspace tools (like synapless) read it without
needing to open hidraw directly. No D-Bus changes, no uinput — just expose the
data and let people build on it.

---

## References

- openrazer Tartarus Pro driver: `driver/razertartaruspro_driver.c`
- openrazer HID report builders: `driver/razerchromacommon.c`
- Tartarus Pro USB IDs: VID `0x1532`, PID `0x0244`
- HID report ID `0x06`, EP2 interrupt IN, 24 bytes total
- Analog pressure: 23 data bytes, one per key/axis, `0x00`=rest `0xFF`=full
- No enable command required — device streams continuously

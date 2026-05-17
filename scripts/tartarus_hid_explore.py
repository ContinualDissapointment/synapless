"""
Razer Tartarus Pro — analog pressure mapper.

Run as Administrator with the Tartarus plugged in.
Reads report ID 0x06 from every readable HID interface and prints a
live diff of bytes that change, so you can map which offset corresponds
to which physical key.

Usage:
    python scripts/tartarus_hid_explore.py
"""

import os
import pathlib
import sys
import time

os.add_dll_directory(str(pathlib.Path(__file__).resolve().parent.parent))
import hid

RAZER_VID        = 0x1532
TARTARUS_PRO_PID = 0x0244
TARGET_REPORT_ID = 0x06
POLL_INTERVAL    = 0.02   # 20 ms — fast enough to catch pressure changes


def find_interfaces():
    devices = hid.enumerate(RAZER_VID, TARTARUS_PRO_PID)
    if not devices:
        print("No Razer Tartarus Pro found. Plug it in and run as Administrator.")
        sys.exit(1)
    return devices


def try_open(path: bytes):
    try:
        d = hid.Device(path=path)
        d.nonblocking = True
        return d
    except Exception as e:
        return None


def read_report6(dev) -> bytes | None:
    try:
        data = dev.read(64)
        if data and data[0] == TARGET_REPORT_ID:
            return bytes(data)
    except Exception:
        pass
    return None


def fmt(b: bytes) -> str:
    return " ".join(f"{x:02x}" for x in b)


def diff_str(prev: bytes, curr: bytes) -> str:
    parts = []
    for i, (a, b) in enumerate(zip(prev[1:], curr[1:]), start=1):
        if a != b:
            parts.append(f"  byte[{i:2d}]: {a:3d} → {b:3d}  (delta {b-a:+d})")
    return "\n".join(parts) if parts else ""


def monitor(dev, label: str):
    print(f"\n{'─'*60}")
    print(f"Monitoring: {label}")
    print(f"Press Tartarus keys at varying pressures. Ctrl+C to quit.")
    print(f"{'─'*60}")

    baseline = None
    last     = None
    t_start  = time.monotonic()

    # Collect a baseline over 1 second of idle
    print("  (hold still for 1s to establish baseline...)")
    while time.monotonic() - t_start < 1.0:
        r = read_report6(dev)
        if r:
            baseline = r
        time.sleep(POLL_INTERVAL)

    if baseline is None:
        print("  No report-6 data received on this interface.")
        return False

    print(f"  Baseline: {fmt(baseline[1:])}\n")
    last = baseline

    try:
        while True:
            r = read_report6(dev)
            if r and r != last:
                d = diff_str(last, r)
                if d:
                    print(d)
                    print(f"    full: {fmt(r[1:])}\n")
                last = r
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass

    return True


def main():
    interfaces = find_interfaces()

    print(f"Found {len(interfaces)} HID interface(s) for Tartarus Pro (PID 0244):\n")
    for d in interfaces:
        print(f"  if={d['interface_number']}  UP=0x{d['usage_page']:04X}  "
              f"U=0x{d['usage']:04X}  path={d['path'].decode(errors='replace')}")

    print()

    for info in interfaces:
        dev = try_open(info['path'])
        if dev is None:
            label = (f"if={info['interface_number']} "
                     f"UP=0x{info['usage_page']:04X} U=0x{info['usage']:04X}")
            print(f"  {label}: could not open (driver has exclusive access)")
            continue

        label = (f"if={info['interface_number']} "
                 f"UP=0x{info['usage_page']:04X} U=0x{info['usage']:04X}")
        got_data = monitor(dev, label)
        dev.close()

        if got_data:
            again = input("\nContinue to next interface? [Y/n] ").strip().lower()
            if again == "n":
                break


if __name__ == "__main__":
    main()

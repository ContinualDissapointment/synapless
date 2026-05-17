## Synapless v0.1.0

Control your Razer Tartarus Pro (and 65+ other Razer devices) on Windows without Razer Synapse.

### Download

- **`synapless.exe`** — standalone Windows executable, no install required

> **Windows Defender / SmartScreen:** the EXE is unsigned. Click **"More info" then "Run anyway"** to proceed. Source is fully open.

### What works

- Full RGB lighting control (static, spectrum, wave, reactive, breathing, starlight, per-key custom frames)
- Macro engine with per-device suppression via kernel filter driver
- Brightness control
- Mouse DPI, polling rate, battery status
- REST API at `http://127.0.0.1:8083` with interactive docs at `/docs`
- Windows Service install/start/stop

### Macro setup (Tartarus Pro) — one-time, requires reboot

Macros require test-signing mode because the kernel filter driver (`kbfiltr.sys`) is self-signed:

```powershell
# Run PowerShell as Administrator
bcdedit /set testsigning on
# Reboot, then:
.\synapless.exe driver install
# Replug the Tartarus Pro
.\synapless.exe debug
# Open http://127.0.0.1:8083 and configure macros
```

A "Test Mode" watermark appears in the desktop corner — cosmetic only. To remove it later: `bcdedit /set testsigning off` after uninstalling the driver.

Macros also work without the driver (fallback hook mode), but the very first keypress after idle will also type the trigger key before the macro fires.

### Supported hardware

65 devices — Tartarus Pro/V2, BlackWidow, Huntsman, Ornata, DeathStalker, Cynosa, Blade laptops, DeathAdder, Viper, Basilisk, Naga, Orochi, Cobra and more. See [README](https://github.com/ContinualDissapointment/synapless#supported-devices-65-total) for full list.

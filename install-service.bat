@echo off
:: Installs synapless as a Windows Service (auto-starts on boot)
:: Must be run as Administrator
cd /d "%~dp0"
python -m service.daemon install
python -m service.daemon start
echo.
echo Service installed and started. Open http://127.0.0.1:8083/ in your browser.
pause

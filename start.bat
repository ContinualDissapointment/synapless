@echo off
cd /d "%~dp0"
python -m service.daemon debug
pause

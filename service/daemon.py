"""
Windows Service wrapper using pywin32.

Install:   python -m service.daemon install
Start:     python -m service.daemon start
Stop:      python -m service.daemon stop
Remove:    python -m service.daemon remove
Debug run: python -m service.daemon debug   (runs in foreground, Ctrl+C to stop)

The service starts the FastAPI server (uvicorn) and the DeviceManager in the
same process. It binds to 127.0.0.1:8083.
"""

import logging
import logging.handlers
import os
import pathlib
import sys
import threading
import time

LOG_DIR = pathlib.Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "openrazer-win" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    handlers=[
        logging.handlers.TimedRotatingFileHandler(
            LOG_DIR / "service.log", when="midnight", backupCount=4, encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Shared run logic ──────────────────────────────────────────────────────────

def run_service() -> None:
    """Start DeviceManager + uvicorn; block until _shutdown_event is set."""
    import uvicorn
    from .device_manager import DeviceManager
    from .macro_manager import MacroManager
    from .api import app, set_manager, set_macro_manager, HOST, PORT

    manager = DeviceManager()
    manager.start()
    set_manager(manager)

    macros = MacroManager()
    macros.start()
    set_macro_manager(macros)

    config = uvicorn.Config(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)

    _shutdown_event.clear()

    def _uvicorn_thread():
        server.run()

    t = threading.Thread(target=_uvicorn_thread, daemon=True)
    t.start()
    log.info("openrazer-win running on http://%s:%d", HOST, PORT)

    _shutdown_event.wait()

    log.info("Shutdown requested, stopping...")
    server.should_exit = True
    t.join(timeout=10)
    macros.stop()
    manager.stop()
    log.info("openrazer-win stopped")


_shutdown_event = threading.Event()


# ── Windows Service (pywin32) ─────────────────────────────────────────────────

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager

    class OpenRazerService(win32serviceutil.ServiceFramework):
        _svc_name_ = "OpenRazerWin"
        _svc_display_name_ = "OpenRazer Windows Service"
        _svc_description_ = "Razer peripheral daemon with REST API (openrazer-win)"

        def __init__(self, args):
            super().__init__(args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            _shutdown_event.set()
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            run_service()

    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False


# ── Debug / standalone run ────────────────────────────────────────────────────

def debug_run() -> None:
    import signal

    def _sigint(sig, frame):
        log.info("Ctrl+C received")
        _shutdown_event.set()

    signal.signal(signal.SIGINT, _sigint)
    run_service()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "debug"

    if cmd == "debug":
        debug_run()
    elif _WIN32_AVAILABLE:
        win32serviceutil.HandleCommandLine(OpenRazerService)
    else:
        print("pywin32 not installed. Run with 'debug' for foreground mode.")
        print("Install pywin32: pip install pywin32")
        sys.exit(1)

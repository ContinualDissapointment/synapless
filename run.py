"""PyInstaller entry point — avoids relative import issues when frozen."""
import sys
import os
import pathlib

# Write crash info to log before anything else can fail
_LOG_DIR = pathlib.Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "openrazer-win" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_CRASH_LOG = _LOG_DIR / "crash.log"

try:
    from service.main import main
    main()
except Exception as exc:
    import traceback
    with open(_CRASH_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        traceback.print_exc(file=f)
    raise

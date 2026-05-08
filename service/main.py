"""Entry point for `synapless` CLI command (defined in pyproject.toml)."""

import sys

try:
    from .daemon import debug_run, _WIN32_AVAILABLE
except ImportError:
    from service.daemon import debug_run, _WIN32_AVAILABLE

USAGE = """\
synapless — Razer peripheral control without Synapse

Usage:
  synapless debug               Run in foreground (Ctrl+C to stop)
  synapless install             Install as Windows Service
  synapless start               Start Windows Service
  synapless stop                Stop Windows Service
  synapless remove              Remove Windows Service
"""


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return

    if args[0] == "debug":
        debug_run()
        return

    if _WIN32_AVAILABLE:
        import win32serviceutil
        from .daemon import OpenRazerService
        sys.argv = [sys.argv[0]] + args
        win32serviceutil.HandleCommandLine(OpenRazerService)
    else:
        print("pywin32 not installed. Only 'debug' mode is available.")
        print("Install: pip install pywin32")
        sys.exit(1)


if __name__ == "__main__":
    main()

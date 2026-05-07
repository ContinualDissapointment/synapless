import os
import sys

# When frozen by PyInstaller, binaries land in _MEIPASS but Windows DLL
# search doesn't include it by default. Add it so hidapi.dll is found.
if sys.platform == 'win32' and hasattr(sys, '_MEIPASS'):
    os.add_dll_directory(sys._MEIPASS)

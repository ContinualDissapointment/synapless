# PyInstaller spec for synapless.exe
# Run: pyinstaller synapless.spec

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect the entire hid package including hidapi.dll
hid_datas, hid_binaries, hid_hidden = collect_all('hid')

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=hid_binaries,
    datas=hid_datas + [('service/static', 'service/static')],
    hiddenimports=hid_hidden + [
        # pywin32 service support
        'win32timezone',
        'win32service',
        'win32serviceutil',
        'win32event',
        'servicemanager',
        'pywintypes',
        # uvicorn dynamic imports
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # async runtime
        'anyio',
        'anyio._backends._asyncio',
        # fastapi / starlette / pydantic
        'fastapi',
        'starlette',
        'starlette.routing',
        'pydantic',
        'pydantic.deprecated.class_validators',
        'email_validator',
    ],
    hookspath=[],
    runtime_hooks=['rthooks/add_dll_dir.py'],
    excludes=['tkinter', 'test', 'unittest'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='synapless',
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    uac_admin=True,
    icon=None,
)

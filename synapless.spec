# PyInstaller spec for synapless.exe
# Run: pyinstaller synapless.spec

block_cipher = None

a = Analysis(
    ['service/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
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
        # hid / hidapi
        'hid',
    ],
    hookspath=[],
    runtime_hooks=[],
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
    console=True,        # keep console so service output is visible
    uac_admin=True,      # request elevation prompt on launch
    icon=None,
)

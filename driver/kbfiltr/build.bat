@echo off
setlocal

rem ── Paths ─────────────────────────────────────────────────────────────────────
set VS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat
set WINKIT=C:\Program Files (x86)\Windows Kits\10
set WDKVER=10.0.26100.0

if not exist "%VS%" (
    echo ERROR: VS 2022 Community not found at expected path.
    exit /b 1
)

rem ── Set up x64 compiler environment ──────────────────────────────────────────
call "%VS%" x64 >nul 2>&1

rem ── Include and lib paths ────────────────────────────────────────────────────
set INC=/I"%WINKIT%\Include\%WDKVER%\km" ^
        /I"%WINKIT%\Include\%WDKVER%\shared" ^
        /I"%WINKIT%\Include\%WDKVER%\ucrt"

set LIBS="%WINKIT%\Lib\%WDKVER%\km\x64\ntoskrnl.lib" ^
         "%WINKIT%\Lib\%WDKVER%\km\x64\hal.lib" ^
         "%WINKIT%\Lib\%WDKVER%\km\x64\wdm.lib" ^
         "%WINKIT%\Lib\%WDKVER%\km\x64\BufferOverflowK.lib"

rem ── Compiler flags ────────────────────────────────────────────────────────────
rem   /kernel   - kernel-mode compilation (disables SEH, float, intrinsics)
rem   /GS-      - no buffer-security-check (requires CRT, unavailable in kernel)
rem   /Gy       - function-level linking
rem   /GF       - string pooling
rem   /W4 /WX   - warnings as errors
rem   /O1       - optimise for size
rem   /Zp8      - pack structs to 8 bytes (kernel convention)
set CFLAGS=/GS- /Gy /GF /W4 /WX /O1 /Zp8 /kernel ^
           /D_AMD64_ /D_WIN64 /DNDEBUG /D_UNICODE /DUNICODE ^
           /D_WIN32_WINNT=0x0A00 /DWINVER=0x0A00

rem ── Linker flags ─────────────────────────────────────────────────────────────
rem   /DRIVER          - marks image as kernel driver
rem   /SUBSYSTEM:NATIVE- native executable (no Win32 subsystem)
rem   /ENTRY:DriverEntry - driver entry point (no decoration on x64)
rem   /ALIGN:0x1000    - page-align sections
rem   /MERGE:.rdata=.text - merge read-only data into text (common for drivers)
set LFLAGS=/NODEFAULTLIB /DRIVER /SUBSYSTEM:NATIVE,6.01 /ALIGN:0x1000 ^
           /ENTRY:DriverEntry /MERGE:.rdata=.text ^
           /OUT:kbfiltr.sys

echo [kbfiltr] Compiling...
cl %CFLAGS% %INC% /c kbfiltr.c /Fo:kbfiltr.obj
if errorlevel 1 ( echo COMPILE FAILED & exit /b 1 )

echo [kbfiltr] Linking...
link %LFLAGS% kbfiltr.obj %LIBS%
if errorlevel 1 ( echo LINK FAILED & exit /b 1 )

echo [kbfiltr] Build complete: kbfiltr.sys
endlocal

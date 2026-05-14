@echo off
setlocal

set VS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat
set WINKIT=C:\Program Files (x86)\Windows Kits\10
set WDKVER=10.0.26100.0

call "%VS%" x64
if errorlevel 1 ( echo vcvarsall failed & exit /b 1 )

for /f "delims=" %%V in ('dir /b /ad "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC" 2^>nul ^| sort /r') do (
    set MSVCVER=%%V & goto :found_msvc
)
:found_msvc
set MSVC_INC=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\%MSVCVER%\include

set INC=/I"%MSVC_INC%" /I"%WINKIT%\Include\%WDKVER%\km" /I"%WINKIT%\Include\%WDKVER%\shared" /I"%WINKIT%\Include\%WDKVER%\ucrt"

set LIBS="%WINKIT%\Lib\%WDKVER%\km\x64\ntoskrnl.lib" "%WINKIT%\Lib\%WDKVER%\km\x64\hal.lib" "%WINKIT%\Lib\%WDKVER%\km\x64\wdm.lib" "%WINKIT%\Lib\%WDKVER%\km\x64\BufferOverflowK.lib"

set CFLAGS=/GS- /Gy /GF /W4 /WX /O1 /Zp8 /kernel /D_AMD64_ /D_WIN64 /DNDEBUG /D_UNICODE /DUNICODE /D_WIN32_WINNT=0x0A00 /DWINVER=0x0A00

set LFLAGS=/NODEFAULTLIB /DRIVER /SUBSYSTEM:NATIVE,6.01 /ALIGN:0x1000 /ENTRY:DriverEntry /MERGE:.rdata=.text /OUT:kbfiltr.sys

cd /d C:\Users\Lorem\synapless\driver\kbfiltr

echo [kbfiltr] Compiling...
cl %CFLAGS% %INC% /c kbfiltr.c /Fo:kbfiltr.obj
if errorlevel 1 ( echo COMPILE FAILED & exit /b 1 )

echo [kbfiltr] Linking...
link %LFLAGS% kbfiltr.obj %LIBS%
if errorlevel 1 ( echo LINK FAILED & exit /b 1 )

echo [kbfiltr] Build complete: kbfiltr.sys
endlocal

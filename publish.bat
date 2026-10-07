@echo off
REM ============================================================
REM   Publish the latest built installer to all users
REM   (they get an in-app update notification).
REM   Run build.bat first.
REM ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul

set "PY=C:\WND\p\buildvenv\Scripts\python.exe"
if defined ITSL_BUILDVENV set "PY=%ITSL_BUILDVENV%\Scripts\python.exe"

set /p VERSION=<version.txt
echo Publishing version %VERSION% ...
set /p NOTES=What changed in this version (optional, shown to users):

"%PY%" "%~dp0scripts\publish_release.py" --notes "%NOTES%"

echo.
pause
endlocal

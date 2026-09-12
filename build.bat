@echo off
REM ============================================================
REM   ساخت نصب‌کننده‌ی ITServiceLog با دابل‌کلیک
REM   کافی است این فایل را اجرا کنید. اگر شماره نسخه بخواهید،
REM   می‌پرسد؛ خالی بگذارید تا از version.txt استفاده شود.
REM ============================================================
setlocal
cd /d "%~dp0"

set "VERSION=%~1"
if "%VERSION%"=="" set /p VERSION=Enter build version (or press Enter to keep current):

echo.
if "%VERSION%"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" -Version "%VERSION%"
)

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
    echo ============================================================
    echo   Build finished. The installer is in the  release\  folder.
    echo ============================================================
) else (
    echo ------------------------------------------------------------
    echo   Build FAILED. Scroll up to read the error message.
    echo ------------------------------------------------------------
)
echo.
pause
endlocal

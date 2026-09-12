<#
    Build the offline ITServiceLog installer with a single command.

    Usage:
        powershell -ExecutionPolicy Bypass -File build.ps1
        powershell -ExecutionPolicy Bypass -File build.ps1 -Version 1.2.0

    Steps:
        1) Freeze the code with PyInstaller into a standalone folder (no Python needed)
        2) Inno Setup packs it into a versioned Setup.exe
    Final output:  release\ITServiceLog-Setup-<version>.exe
#>
param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# --- Tool paths (edit here if the environment moves) ---
$Python = "C:\WND\p\buildvenv\Scripts\python.exe"
$ISCC   = "C:\WND\p\innosetup\ISCC.exe"

# --- Resolve version ---
if ([string]::IsNullOrWhiteSpace($Version)) {
    if (Test-Path "$root\version.txt") {
        $Version = (Get-Content "$root\version.txt" -Raw).Trim()
    } else {
        $Version = "1.0.0"
    }
} else {
    # Persist the given version so version.txt stays in sync
    Set-Content -Path "$root\version.txt" -Value $Version -Encoding ascii
}
Write-Host "==> Building version $Version" -ForegroundColor Cyan

# --- Check tools ---
if (-not (Test-Path $Python)) { throw "Build Python not found: $Python" }
if (-not (Test-Path $ISCC))   { throw "Inno Setup compiler not found: $ISCC" }

# --- Step 0: Build the seed (current users + operations) ---
Write-Host "==> Building seed from current database..." -ForegroundColor Cyan
& $Python "assets\make_seed.py"
$seedFile = "$root\assets\seed.sqlite"
$addSeed = Test-Path $seedFile
if ($addSeed) {
    Write-Host "    seed.sqlite included (users + operations will ship)" -ForegroundColor DarkGray
} else {
    Write-Host "    no seed produced; installer will start with a fresh database" -ForegroundColor Yellow
}

# --- Step 1: PyInstaller ---
Write-Host "==> Running PyInstaller..." -ForegroundColor Cyan
if (Test-Path "$root\build") { Remove-Item "$root\build" -Recurse -Force }
if (Test-Path "$root\dist")  { Remove-Item "$root\dist"  -Recurse -Force }

$piArgs = @(
    "-m", "PyInstaller", "--noconfirm", "--clean",
    "--name", "ITServiceLog", "--windowed",
    "--icon", "assets\app.ico",
    "--add-data", "assets\app.ico;assets",
    "--collect-submodules", "sqlalchemy"
)
if ($addSeed) { $piArgs += @("--add-data", "assets\seed.sqlite;assets") }
# نمونه‌ی پیکربندی سرور/دامنه را کنار برنامه می‌گذاریم (installer.iss هم آن را کپی می‌کند)
if (Test-Path "$root\config.example.json") { $piArgs += @("--add-data", "config.example.json;.") }
# اگر pyodbc در محیط build نصب باشد، اتصال به SQL Server هم داخل بسته قرار می‌گیرد
& $Python -c "import pyodbc" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "    pyodbc found; SQL Server support will be bundled" -ForegroundColor DarkGray
    $piArgs += @("--hidden-import", "pyodbc", "--hidden-import", "sqlalchemy.dialects.mssql.pyodbc")
} else {
    Write-Host "    pyodbc not installed in build env; SQL Server support NOT bundled" -ForegroundColor Yellow
}
$piArgs += "main.py"
& $Python @piArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
if (-not (Test-Path "$root\dist\ITServiceLog\ITServiceLog.exe")) { throw "PyInstaller output missing" }

# --- Step 2: Inno Setup ---
Write-Host "==> Building installer with Inno Setup..." -ForegroundColor Cyan
& $ISCC "/DMyAppVersion=$Version" "$root\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

$out = "$root\release\ITServiceLog-Setup-$Version.exe"
if (Test-Path $out) {
    $size = "{0:N1} MB" -f ((Get-Item $out).Length / 1MB)
    Write-Host ""
    Write-Host "==> Done! Installer ready ($size):" -ForegroundColor Green
    Write-Host "    $out" -ForegroundColor Green
} else {
    throw "Installer file was not produced"
}

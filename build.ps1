<#
    Build the offline ITServiceLog installer with a single command.

    Easiest: just double-click  build.bat

    Or from a terminal:
        powershell -ExecutionPolicy Bypass -File build.ps1
        powershell -ExecutionPolicy Bypass -File build.ps1 -Version 1.2.2

    The build virtualenv and all dependencies are created automatically on the
    first run. Requirements on the machine: Python 3 (python.org) and
    Inno Setup 6 (jrsoftware.org). Override tool locations if needed with the
    ITSL_BUILDVENV and ITSL_ISCC environment variables.

    Steps:
        1) Freeze the code with PyInstaller into a standalone folder (no Python needed)
        2) Inno Setup packs it into a versioned Setup.exe
    Final output:  release\ITServiceLog-Setup-<version>.exe
#>
param(
    [string]$Version = "",
    # آدرس دیتابیس سرور که داخل بسته به‌صورت config.json قرار می‌گیرد.
    # اگر ندهید، از فایل deploy.json کنار پروژه خوانده می‌شود (در گیت نیست).
    [string]$DbUrl = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# --- Tool locations (override with environment variables if the machine differs) ---
$VenvDir = if ($env:ITSL_BUILDVENV) { $env:ITSL_BUILDVENV } else { "C:\WND\p\buildvenv" }
$Python  = Join-Path $VenvDir "Scripts\python.exe"

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

# --- Ensure the build virtualenv exists (one-time automatic setup) ---
if (-not (Test-Path $Python)) {
    Write-Host "==> Build environment not found; creating it (one-time, may take a few minutes)..." -ForegroundColor Cyan
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $VenvDir
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv $VenvDir
    } else {
        throw "Python 3 not found. Install Python 3 from python.org, then run this again."
    }
    if (-not (Test-Path $Python)) { throw "Failed to create build environment at $VenvDir" }

    Write-Host "==> Installing build dependencies..." -ForegroundColor Cyan
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r "$root\requirements.txt"
    # ابزار بسته‌بندی + درایورهای دیتابیس سرور (PostgreSQL و SQL Server)
    & $Python -m pip install pyinstaller psycopg2-binary pyodbc
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
} else {
    # اطمینان از نصب بودن ابزار بسته‌بندی حتی اگر venv از قبل ساخته شده بود
    & $Python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "==> Installing missing build tools..." -ForegroundColor Cyan
        & $Python -m pip install pyinstaller psycopg2-binary
    }
}

# --- Locate the Inno Setup compiler (ISCC.exe) ---
$ISCC = $null
$isccCandidates = @(
    $env:ITSL_ISCC,
    "C:\WND\p\innosetup\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
foreach ($c in $isccCandidates) {
    if ($c -and (Test-Path $c)) { $ISCC = $c; break }
}
if (-not $ISCC) {
    throw "Inno Setup compiler (ISCC.exe) not found. Install Inno Setup 6 from jrsoftware.org, " +
          "or set the ITSL_ISCC environment variable to its full path."
}

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
# اگر psycopg2 در محیط build نصب باشد، اتصال به PostgreSQL داخل بسته قرار می‌گیرد
& $Python -c "import psycopg2" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "    psycopg2 found; PostgreSQL support will be bundled" -ForegroundColor DarkGray
    $piArgs += @("--hidden-import", "psycopg2", "--hidden-import", "sqlalchemy.dialects.postgresql.psycopg2")
} else {
    Write-Host "    psycopg2 not installed in build env; PostgreSQL support NOT bundled" -ForegroundColor Yellow
}
# اگر pyodbc هم نصب باشد، اتصال به SQL Server نیز پشتیبانی می‌شود (اختیاری)
& $Python -c "import pyodbc" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "    pyodbc found; SQL Server support will be bundled" -ForegroundColor DarkGray
    $piArgs += @("--hidden-import", "pyodbc", "--hidden-import", "sqlalchemy.dialects.mssql.pyodbc")
}
$piArgs += "main.py"
& $Python @piArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
if (-not (Test-Path "$root\dist\ITServiceLog\ITServiceLog.exe")) { throw "PyInstaller output missing" }

# --- Step 1.5: Bake config.json (server db_url) into the package ---
# مقدار از پارامتر -DbUrl یا از فایل deploy.json (خارج از گیت) خوانده می‌شود.
$deployUrl = $DbUrl
if ([string]::IsNullOrWhiteSpace($deployUrl) -and (Test-Path "$root\deploy.json")) {
    try { $deployUrl = (Get-Content "$root\deploy.json" -Raw | ConvertFrom-Json).db_url } catch {}
}
if (-not [string]::IsNullOrWhiteSpace($deployUrl)) {
    $cfg = @{ db_url = $deployUrl } | ConvertTo-Json
    Set-Content -Path "$root\dist\ITServiceLog\config.json" -Value $cfg -Encoding utf8
    Write-Host "    config.json baked with server db_url" -ForegroundColor DarkGray
} else {
    Write-Host "    no db_url provided (-DbUrl or deploy.json); installer ships WITHOUT config.json" -ForegroundColor Yellow
}

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

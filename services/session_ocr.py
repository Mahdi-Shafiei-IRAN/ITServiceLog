"""
OCRِ یک فایلِ تصویری با موتور داخلی ویندوز (WinRT / Windows.Media.Ocr).
هیچ نصبی لازم نیست. کپچرِ تصویر جداست (services/screen_capture.py) تا همان
تصویر هم برای OCR و هم برای مدلِ تصویری قابل‌استفاده باشد.
در هر خطا رشتهٔ خالی برمی‌گرداند.
"""
import os
import sys
import subprocess

from services import screen_capture

_MARKER = "<<<ITSL_OCR>>>"

_PS_OCR = r"""
param([string]$Path)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
Add-Type -AssemblyName System.Runtime.WindowsRuntime
try {
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    function Await($op, $t) {
        $x = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $x.Wait(-1) | Out-Null; $x.Result
    }
    [Windows.Media.Ocr.OcrEngine,            Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Storage.StorageFile,            Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    $file    = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
    $stream  = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap  = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $engine  = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    Write-Output '<<<ITSL_OCR>>>'
    if ($engine -ne $null) {
        $r = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        Write-Output $r.Text
    }
    $stream.Dispose()
} catch { Write-Output '<<<ITSL_OCR>>>' }
"""


def is_supported():
    return sys.platform.startswith("win")


def _script_path():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "ITServiceLog", "_ocr_file.ps1")


def _ensure_script():
    path = _script_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                if f.read() == _PS_OCR:
                    return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_PS_OCR)
        return path
    except Exception:
        return None


def ocr_file(png_path, timeout=12):
    """متنِ OCRِ یک فایل PNG را برمی‌گرداند (یا رشتهٔ خالی)."""
    if not png_path or not os.path.exists(png_path) or not is_supported():
        return ""
    path = _ensure_script()
    if not path:
        return ""
    try:
        creationflags = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", path, "-Path", png_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=creationflags)
        out = proc.stdout or ""
        if _MARKER in out:
            return out.split(_MARKER, 1)[1].strip()
        return ""
    except Exception:
        return ""


def capture_and_ocr(hwnd, timeout=12):
    """سازگاری: از پنجره عکس می‌گیرد و OCR می‌کند. مسیر تصویر را هم نگه نمی‌دارد."""
    path = screen_capture.capture_window(hwnd)
    if not path:
        return ""
    try:
        return ocr_file(path, timeout=timeout)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

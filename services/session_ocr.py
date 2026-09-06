"""
گرفتن تصویر از یک ناحیهٔ صفحه و متن‌کاویِ آن با موتور OCRِ داخلی ویندوز.

هیچ نصبی لازم نیست: از PowerShell (روی هر ویندوز ۱۰/۱۱ هست) و WinRT
(Windows.Media.Ocr) استفاده می‌کنیم. زبان‌های OCR همان‌هایی‌اند که روی
سیستمِ کارشناس نصب‌اند (انگلیسی به‌صورت پیش‌فرض موجود است). اگر به هر دلیلی
شکست بخورد، رشتهٔ خالی برمی‌گرداند و هیچ خطایی به بالا پرت نمی‌شود.
"""
import os
import sys
import subprocess

_MARKER = "<<<ITSL_OCR>>>"

# اسکریپت PowerShell که یک مستطیل از صفحه را می‌گیرد، PNG می‌کند و OCR می‌کند.
_PS_SCRIPT = r"""
param([int]$Left,[int]$Top,[int]$Width,[int]$Height)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime
try {
    $bmp = New-Object System.Drawing.Bitmap $Width, $Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($Left, $Top, 0, 0, (New-Object System.Drawing.Size $Width, $Height))
    $g.Dispose()
    $tmp = [System.IO.Path]::Combine($env:TEMP, ('itsl_ocr_' + [System.Guid]::NewGuid().ToString('N') + '.png'))
    $bmp.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()

    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    function Await($op, $t) {
        $x = $asTask.MakeGenericMethod($t).Invoke($null, @($op))
        $x.Wait(-1) | Out-Null
        $x.Result
    }

    [Windows.Media.Ocr.OcrEngine,            Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Storage.StorageFile,            Windows.Foundation, ContentType=WindowsRuntime] | Out-Null

    $file    = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($tmp)) ([Windows.Storage.StorageFile])
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
    Remove-Item $tmp -ErrorAction SilentlyContinue
} catch {
    Write-Output '<<<ITSL_OCR>>>'
}
"""


def _script_path():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "ITServiceLog", "_capture_ocr.ps1")


def _ensure_script():
    """اسکریپت PowerShell را یک‌بار روی دیسک می‌نویسد (اگر نبود یا فرق داشت)."""
    path = _script_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                if f.read() == _PS_SCRIPT:
                    return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_PS_SCRIPT)
        return path
    except Exception:
        return None


def is_supported():
    """آیا این پلتفرم از OCR پشتیبانی می‌کند؟ (فعلاً فقط ویندوز)"""
    return sys.platform.startswith("win")


def capture_and_ocr(rect, timeout=12):
    """
    ناحیهٔ (left, top, width, height) از صفحه را می‌گیرد و متنِ OCR را برمی‌گرداند.
    در هر خطایی رشتهٔ خالی برمی‌گرداند (هرگز استثنا پرت نمی‌کند).
    """
    if not rect or not is_supported():
        return ""
    left, top, width, height = rect
    if width <= 0 or height <= 0:
        return ""
    path = _ensure_script()
    if not path:
        return ""
    try:
        # CREATE_NO_WINDOW تا پنجرهٔ کنسول جلوی چشم کاربر باز/بسته نشود.
        creationflags = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", path,
             "-Left", str(int(left)), "-Top", str(int(top)),
             "-Width", str(int(width)), "-Height", str(int(height))],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=creationflags)
        out = proc.stdout or ""
        if _MARKER in out:
            return out.split(_MARKER, 1)[1].strip()
        return ""
    except Exception:
        return ""

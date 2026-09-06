"""
عکس‌گرفتن از یک پنجرهٔ مشخص (نه از مختصاتِ صفحه).

روشِ اصلی PrintWindow با پرچمِ PW_RENDERFULLCONTENT است که پیکسل‌های خودِ
پنجرهٔ هدف را می‌گیرد — حتی اگر پنجرهٔ دیگری رویش باشد یا فوکوس جای دیگر باشد.
اگر نتیجه سیاه/خالی درآمد (بعضی کنترل‌های ریموت این‌طورند)، به CopyFromScreen
از مستطیلِ همان پنجره برمی‌گردیم. خروجی PNG است تا هم برای OCR و هم برای مدلِ
تصویری قابل‌استفاده باشد. در هر خطا None برمی‌گرداند.
"""
import os
import sys
import uuid
import subprocess

from services.remote_detector import get_window_rect, is_offscreen_rect
from services.debug_log import log

# آستانهٔ حجمِ فایل: PNGِ تقریباً سیاه خیلی کوچک است؛ زیرِ این حد یعنی کپچر خراب.
_MIN_PNG_BYTES = 6000

_PS_PRINTWINDOW = r"""
param([long]$Hwnd,[string]$Out)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
Add-Type -AssemblyName System.Drawing
$sig = @'
using System;
using System.Runtime.InteropServices;
public class ItslCap {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
  [StructLayout(LayoutKind.Sequential)] public struct R { public int L, T, Rt, B; }
}
'@
Add-Type -TypeDefinition $sig
try {
    $h = [IntPtr]$Hwnd
    $r = New-Object ItslCap+R
    [ItslCap]::GetWindowRect($h, [ref]$r) | Out-Null
    $w = $r.Rt - $r.L; $ht = $r.B - $r.T
    if ($w -le 0 -or $ht -le 0) { Write-Output 'BADRECT'; exit }
    $bmp = New-Object System.Drawing.Bitmap $w, $ht
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    $ok = [ItslCap]::PrintWindow($h, $hdc, 2)   # PW_RENDERFULLCONTENT
    $g.ReleaseHdc($hdc); $g.Dispose()
    $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Output ($(if ($ok) {'OK'} else {'PWFAIL'}))
} catch { Write-Output 'ERR' }
"""

_PS_COPYSCREEN = r"""
param([int]$Left,[int]$Top,[int]$Width,[int]$Height,[string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
try {
    $bmp = New-Object System.Drawing.Bitmap $Width, $Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($Left, $Top, 0, 0, (New-Object System.Drawing.Size $Width, $Height))
    $g.Dispose()
    $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Output 'OK'
} catch { Write-Output 'ERR' }
"""


def is_supported():
    return sys.platform.startswith("win")


def _appdir():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "ITServiceLog")
    os.makedirs(d, exist_ok=True)
    return d


def _ensure(name, content):
    path = os.path.join(_appdir(), name)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                if f.read() == content:
                    return path
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
    except Exception:
        return None


def _run_ps(script_path, args, timeout=15):
    creationflags = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", script_path] + args,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=creationflags)
        return (proc.stdout or "").strip()
    except Exception as e:
        log(f"capture: powershell error: {e!r}")
        return ""


def capture_window(hwnd, out_path=None):
    """
    از پنجرهٔ hwnd یک PNG می‌سازد و مسیرش را برمی‌گرداند (یا None).
    اول PrintWindow؛ اگر خروجی خیلی کوچک/سیاه بود، CopyFromScreen.
    """
    if not hwnd or not is_supported():
        return None
    rect = get_window_rect(hwnd)
    if is_offscreen_rect(rect):
        log(f"capture: پنجره مینیمایز/نامعتبر (hwnd={hwnd} rect={rect})")
        return None
    if out_path is None:
        out_path = os.path.join(_appdir(), "_frames", uuid.uuid4().hex + ".png")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # ۱) PrintWindow
    p = _ensure("_capture_pw.ps1", _PS_PRINTWINDOW)
    status = _run_ps(p, ["-Hwnd", str(int(hwnd)), "-Out", out_path]) if p else ""
    size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
    log(f"capture: printwindow status={status} bytes={size} hwnd={hwnd}")
    if size >= _MIN_PNG_BYTES:
        return out_path

    # ۲) fallback: CopyFromScreen از مستطیلِ پنجره
    left, top, w, h = rect
    p2 = _ensure("_capture_cs.ps1", _PS_COPYSCREEN)
    status2 = _run_ps(p2, ["-Left", str(left), "-Top", str(top),
                           "-Width", str(w), "-Height", str(h), "-Out", out_path]) if p2 else ""
    size2 = os.path.getsize(out_path) if os.path.exists(out_path) else 0
    log(f"capture: copyscreen status={status2} bytes={size2}")
    if size2 > 0:
        return out_path
    return None

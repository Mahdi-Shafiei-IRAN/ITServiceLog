"""
تشخیص خودکار دستگاهی که از طریق DameWare به آن متصل هستیم.

روش کار: عنوان پنجره‌های باز ویندوز را می‌خوانیم، پنجره‌های مربوط به
DameWare را پیدا می‌کنیم و نام/IP دستگاه مقصد را از عنوان آن‌ها استخراج
می‌کنیم. سپس در صورت امکان نام را به IP (یا برعکس) تبدیل می‌کنیم.

هیچ وابستگی خارجی لازم نیست؛ فقط ctypes (ویندوز) و socket.
تنظیمات قابل ویرایش در فایل remote_config.json کنار دیتابیس ذخیره می‌شود،
تا اگر عنوان پنجرهٔ نسخهٔ DameWare شما فرق داشت، بدون build مجدد قابل تنظیم باشد.
"""
import os
import re
import json
import socket
import subprocess
import sys

# پورت‌های پیش‌فرضِ DameWare Mini Remote Control (کلاینت به این پورت‌ها روی
# دستگاه مقصد وصل می‌شود). «وصل بودن» را از روی اتصالِ واقعیِ TCP می‌سنجیم،
# نه عنوانِ پنجره — چون DameWare پس از قطع، پنجره را با نامِ آخرین سیستم باز
# نگه می‌دارد و تشخیصِ مبتنی بر عنوان را گمراه می‌کند.
DEFAULT_DAMEWARE_PORTS = [6129, 6130, 6132, 6133]

# --- تنظیمات پیش‌فرض ---
# نام فایل اجراییِ نرم‌افزار ریموت. DWRCC.exe همان کلاینت Mini Remote Control است
# که پنجرهٔ دسکتاپ راه دور را باز می‌کند. فیلتر بر اساس پروسه، از مثبتِ کاذبِ
# مرورگر/پنجره‌های نامرتبط جلوگیری می‌کند.
DEFAULT_PROCESSES = ["DWRCC.exe", "DWRCS.exe", "DameWare.exe", "DNTU.exe"]

# عبارت‌هایی که در عنوان پنجرهٔ DameWare دیده می‌شوند (حساس به بزرگی/کوچکی نیست).
# فقط به‌عنوان fallback وقتی نام پروسه قابل تشخیص نباشد استفاده می‌شود.
DEFAULT_MARKERS = ["DameWare", "Mini Remote Control", "Remote Support", "MRC"]

# کلماتی که باید هنگام استخراجِ «نام سیستم» از عنوان نادیده گرفته شوند.
DEFAULT_STOPWORDS = [
    "DameWare", "Mini", "Remote", "Control", "Support", "MRC",
    "Host", "Connected", "to", "Session", "Viewer", "-", "|",
]

_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{1,62}$")


def _config_path():
    app_data = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(app_data, "ITServiceLog", "remote_config.json")


def load_config():
    """تنظیمات را از فایل می‌خواند؛ در صورت نبود، پیش‌فرض‌ها را می‌سازد."""
    cfg = {
        "processes": DEFAULT_PROCESSES,
        "markers": DEFAULT_MARKERS,
        "stopwords": DEFAULT_STOPWORDS,
    }
    path = _config_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            if isinstance(user_cfg.get("processes"), list) and user_cfg["processes"]:
                cfg["processes"] = user_cfg["processes"]
            if isinstance(user_cfg.get("markers"), list) and user_cfg["markers"]:
                cfg["markers"] = user_cfg["markers"]
            if isinstance(user_cfg.get("stopwords"), list):
                cfg["stopwords"] = user_cfg["stopwords"]
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        # اگر خواندن/نوشتن تنظیمات به هر دلیلی شکست خورد، از پیش‌فرض استفاده کن.
        pass
    return cfg


def list_windows():
    """
    پنجره‌های visible ویندوز را همراه نام پروسهٔ صاحبشان برمی‌گرداند (فقط ویندوز).
    خروجی: لیستی از دیکشنری‌ها با کلیدهای title و process.
    """
    windows = []
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # امضای صحیح توابع تا روی ویندوز ۶۴بیتی handle درست منتقل شود.
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        def _text(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value

        def _proc_name(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return ""
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not h:
                return ""
            try:
                size = wintypes.DWORD(260)
                buf = ctypes.create_unicode_buffer(size.value)
                if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    return os.path.basename(buf.value)
                return ""
            finally:
                kernel32.CloseHandle(h)

        EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _cb(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd):
                t = _text(hwnd)
                if t:
                    windows.append({"title": t, "process": _proc_name(hwnd), "hwnd": int(hwnd)})
            return True

        user32.EnumWindows(EnumProc(_cb), 0)
    except Exception:
        # روی سیستم‌عامل غیرویندوزی یا در صورت خطا، لیست خالی برمی‌گردد.
        pass
    return windows


def list_window_titles():
    """فقط عنوان‌ها (برای سازگاری و ابزار عیب‌یابی)."""
    return [w["title"] for w in list_windows()]


def get_window_rect(hwnd):
    """
    مختصات پنجره را به شکل (left, top, width, height) برمی‌گرداند.
    در صورت نامعتبر بودن یا خطا None برمی‌گرداند (فقط ویندوز).
    """
    if not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        rect = wintypes.RECT()
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w <= 0 or h <= 0:
            return None
        return (rect.left, rect.top, w, h)
    except Exception:
        return None


def is_offscreen_rect(rect):
    """
    آیا مستطیل برای عکس‌گرفتن نامناسب است؟ (پنجرهٔ مینیمایز در ویندوز روی
    مختصاتِ ~ -32000 می‌رود؛ پنجرهٔ خیلی کوچک هم عملاً بی‌فایده است.)
    """
    if not rect:
        return True
    left, top, w, h = rect
    return left <= -30000 or top <= -30000 or w < 40 or h < 20


def parse_host_from_title(title, stopwords):
    """
    از یک عنوان پنجره، (نام, IP) را استخراج می‌کند. هر کدام که پیدا نشود None است.
    """
    ip = None
    m = _IPV4_RE.search(title)
    if m:
        octets = m.group(0).split(".")
        if all(0 <= int(o) <= 255 for o in octets):
            ip = m.group(0)

    # نام سیستم: فقط روی فاصله می‌شکنیم تا خط‌تیرهٔ داخل نامِ میزبان
    # (مثل PC-ACCOUNTING01) حفظ شود؛ سپس نشانه‌های جداکنندهٔ کناری را پاک می‌کنیم.
    name = None
    low_stop = {w.lower() for w in stopwords}
    for raw in title.split():
        tok = raw.strip(":>|-").strip()
        if not tok or tok.lower() in low_stop:
            continue
        if ip and tok == ip:
            continue
        if _HOSTNAME_RE.match(tok) and not _IPV4_RE.fullmatch(tok):
            name = tok
            break
    return name, ip


def _resolve(name, ip):
    """در صورت امکان نام↔IP را کامل می‌کند (با مهلت کوتاه برای جلوگیری از هنگ)."""
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(1.5)
        if ip and not name:
            try:
                name = socket.gethostbyaddr(ip)[0]
            except Exception:
                pass
        if name and not ip:
            try:
                ip = socket.gethostbyname(name)
            except Exception:
                pass
    finally:
        socket.setdefaulttimeout(old_timeout)
    return name, ip


def detect_sessions(resolve=True):
    """
    نشست‌های فعال DameWare را تشخیص می‌دهد.
    خروجی: لیستی از دیکشنری‌ها با کلیدهای title, name, ip.
    """
    cfg = load_config()
    processes = {p.lower() for p in cfg["processes"]}
    markers = [m.lower() for m in cfg["markers"]]
    stopwords = cfg["stopwords"]

    sessions = []
    seen = set()
    for w in list_windows():
        title = w["title"]
        proc = (w.get("process") or "").lower()

        # فیلتر اصلی: پنجره باید متعلق به پروسهٔ واقعی DameWare باشد.
        # اگر نام پروسه اصلاً قابل تشخیص نبود (proc خالی)، به مارکرِ عنوان برمی‌گردیم؛
        # اما یک پروسهٔ شناخته‌شدهٔ دیگر (مثل مرورگر) هرگز قبول نمی‌شود.
        if proc in processes:
            pass
        elif proc == "" and any(mk in title.lower() for mk in markers):
            pass
        else:
            continue

        name, ip = parse_host_from_title(title, stopwords)
        if not name and not ip:
            continue  # پنجرهٔ کنسول اصلی DameWare بدون میزبان
        if resolve:
            name, ip = _resolve(name, ip)
        key = (name or "", ip or "")
        if key in seen:
            continue
        seen.add(key)
        sessions.append({"title": title, "name": name, "ip": ip,
                         "process": w.get("process"), "hwnd": w.get("hwnd")})
    return sessions


def get_remote_connections(ports=None):
    """
    IPهای مقصدِ اتصال‌های فعالِ TCP (ESTABLISHED) روی پورت‌های DameWare را
    از خروجیِ netstat می‌خواند. اگر لیست خالی بود، یعنی به کسی وصل نیستیم.
    فقط ویندوز؛ در هر خطا لیستِ خالی برمی‌گرداند.
    """
    if ports is None:
        ports = DEFAULT_DAMEWARE_PORTS
    port_set = {int(p) for p in ports}
    ips = []
    if not sys.platform.startswith("win"):
        return ips
    try:
        creationflags = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        out = subprocess.run(
            ["netstat", "-n", "-p", "TCP"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=6, creationflags=creationflags).stdout or ""
        for line in out.splitlines():
            parts = line.split()
            # ستون‌ها: Proto  LocalAddress  ForeignAddress  State
            if len(parts) >= 4 and parts[0].upper() == "TCP" and parts[3].upper() == "ESTABLISHED":
                foreign = parts[2]
                ip, sep, port = foreign.rpartition(":")
                if sep and port.isdigit() and int(port) in port_set:
                    ips.append(ip)
    except Exception:
        pass
    return ips


def is_remote_connected(ports=None):
    """آیا هم‌اکنون یک اتصالِ فعالِ DameWare برقرار است؟"""
    return bool(get_remote_connections(ports))


def format_system_label(name, ip):
    """برچسب یکپارچه برای فیلد «سیستم / IP» می‌سازد."""
    if name and ip:
        return f"{name} ({ip})"
    return name or ip or ""


# پیشوندهای رایجِ نام سیستم که بخشی از نام شخص نیستند و باید حذف شوند.
_NAME_PREFIXES = {
    "it", "pc", "sys", "system", "desktop", "laptop", "ws", "pcs",
    "comp", "computer", "srv", "server", "user", "client", "win", "node",
}


def derive_person_name(system_text):
    """
    نام تقریبیِ شخص را از روی نام سیستم حدس می‌زند.
    قرارداد رایج «it-<نام>» است؛ مثلاً it-sadeghi → Sadeghi.
    اگر چیزی برای استخراج نبود (مثلاً فقط IP)، رشتهٔ خالی برمی‌گرداند.
    """
    if not system_text:
        return ""
    # حذف بخش «(IP)» و هر IP موجود در متن
    s = system_text.split("(")[0]
    s = _IPV4_RE.sub("", s).strip()
    if not s:
        return ""
    # شکستن روی جداکننده‌های رایجِ نام سیستم
    parts = [p for p in re.split(r"[-_./\\\s]+", s) if p]
    # حذف توکن‌های پیشوندی و توکن‌های صرفاً عددی
    meaningful = [p for p in parts if p.lower() not in _NAME_PREFIXES and not p.isdigit()]
    if not meaningful:
        return ""
    # حذف اعداد انتهایی هر توکن (مثلاً sadeghi01 → sadeghi)
    cleaned = [re.sub(r"\d+$", "", p) or p for p in meaningful]
    return " ".join(cleaned).title()

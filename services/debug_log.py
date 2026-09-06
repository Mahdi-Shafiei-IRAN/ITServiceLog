"""
لاگِ سادهٔ فایل برای عیب‌یابیِ دستیارِ خودکار (تشخیص اتصال/قطع، OCR، پیشنهاد).
مسیر: AppData\\Roaming\\ITServiceLog\\session_ai.log
هرگز استثنا پرت نمی‌کند و اگر بزرگ شد، خودش را کوتاه می‌کند.
"""
import os
import datetime

_MAX_BYTES = 1_000_000


def log_path():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "ITServiceLog", "session_ai.log")


def log(msg):
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # اگر فایل خیلی بزرگ شد، از نو شروع کن تا دیسک پر نشود.
        try:
            if os.path.exists(path) and os.path.getsize(path) > _MAX_BYTES:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("--- log truncated ---\n")
        except Exception:
            pass
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{stamp}  {msg}\n")
    except Exception:
        pass

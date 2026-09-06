"""
ناظرِ جلسهٔ ریموت: در پس‌زمینه، «وصل/قطع بودن» را از روی اتصالِ واقعیِ TCP
(پورت‌های DameWare) تشخیص می‌دهد — نه عنوانِ پنجره، چون DameWare بعد از قطع،
پنجره را با نامِ آخرین سیستم باز نگه می‌دارد. در طولِ اتصال هر چند ثانیه از
پنجرهٔ ریموت OCR می‌گیرد و متن را جمع می‌کند؛ به‌محضِ قطعِ اتصال، سیگنالِ
session_ended را با کلِ شواهد می‌فرستد تا صفحهٔ ثبت، توضیح و تیک‌ها را پیش‌پُر کند.

روی یک نخِ جدا اجرا می‌شود تا رابطِ کاربری هرگز کند/قفل نشود. همه‌چیز در
session_ai.log لاگ می‌شود تا عیب‌یابی ساده باشد.
"""
import time
import threading
from PySide6.QtCore import QThread, Signal

from services.remote_detector import (detect_sessions, get_window_rect,
                                       format_system_label, get_remote_connections,
                                       is_offscreen_rect)
from services import session_ocr, task_inference
from services.debug_log import log

_MAX_LINES = 500
_POLL_SECONDS = 3


class SessionWatcher(QThread):
    # (متنِ شواهد, اطلاعاتِ سیستم) — هنگامِ پایانِ یک جلسهٔ دارای شواهد
    session_ended = Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = task_inference.load_config()
        self.enabled = bool(cfg.get("enabled", True)) and session_ocr.is_supported()
        self.interval = max(3, int(cfg.get("interval_seconds", 8)))
        self.ports = cfg.get("dameware_ports") or None
        self._stop = False
        self._lock = threading.Lock()
        self._active = None  # dict یا None

    # --------- حلقهٔ نخِ پس‌زمینه ---------
    def run(self):
        if not self.enabled:
            log("watcher: disabled (enabled=false یا پلتفرم پشتیبانی نمی‌شود)")
            return
        log(f"watcher: started interval={self.interval}s ports={self.ports or 'default'}")
        while not self._stop:
            try:
                self._tick()
            except Exception as e:
                log(f"watcher: tick error: {e!r}")
            self._sleep(_POLL_SECONDS)
        log("watcher: stopped")

    def _sleep(self, seconds):
        slept = 0.0
        while slept < seconds and not self._stop:
            time.sleep(0.25)
            slept += 0.25

    def _tick(self):
        conn_ips = get_remote_connections(self.ports)
        connected = bool(conn_ips)
        try:
            sessions = detect_sessions(resolve=False)
        except Exception:
            sessions = []
        primary = sessions[0] if sessions else None

        active_key = self._active["key"] if self._active else None
        log(f"tick connected={connected} conn_ips={conn_ips} "
            f"windows={[(s.get('name'), s.get('ip')) for s in sessions]} active={active_key}")

        if connected:
            name = primary.get("name") if primary else None
            ip = (primary.get("ip") if primary else None) or (conn_ips[0] if conn_ips else None)
            hwnd = primary.get("hwnd") if primary else None
            key = ip or name or "session"

            if not self._active or self._active["key"] != key:
                self._finalize("switch")
                with self._lock:
                    self._active = {"key": key, "hwnd": hwnd, "name": name, "ip": ip,
                                    "evidence": [], "seen": set(), "last": 0.0}
                log(f"session: started key={key} name={name} ip={ip} hwnd={hwnd}")
            elif hwnd:
                self._active["hwnd"] = hwnd  # پنجره تازه پیدا شد

            now = time.time()
            if now - self._active["last"] >= self.interval:
                self._active["last"] = now
                self._capture()
        else:
            if self._active:
                self._finalize("disconnected")

    def _capture(self):
        hwnd = self._active.get("hwnd")
        rect = get_window_rect(hwnd) if hwnd else None
        if is_offscreen_rect(rect):
            log(f"capture: پنجره نامناسب برای عکس (hwnd={hwnd} rect={rect}) — "
                f"احتمالاً مینیمایز/پنهان است")
            return
        text = session_ocr.capture_and_ocr(rect)
        sample = (text[:80].replace("\n", " ")) if text else ""
        log(f"capture: rect={rect} ocr_chars={len(text)} sample={sample!r}")
        if not text:
            return
        added = 0
        with self._lock:
            buf = self._active["evidence"]
            seen = self._active["seen"]
            for line in text.splitlines():
                line = " ".join(line.split())
                if len(line) < 3:
                    continue
                k = line.lower()
                if k in seen:
                    continue
                seen.add(k)
                buf.append(line)
                added += 1
                if len(buf) > _MAX_LINES:
                    buf.pop(0)
        log(f"capture: +{added} خطِ جدید، مجموع={len(self._active['evidence'])}")

    def _finalize(self, reason=""):
        with self._lock:
            active = self._active
            self._active = None
        if active and active["evidence"]:
            info = {
                "name": active["name"],
                "ip": active["ip"],
                "label": format_system_label(active["name"], active["ip"]),
            }
            log(f"session: ended ({reason}) خطوطِ شواهد={len(active['evidence'])} → ارسالِ پیشنهاد")
            self.session_ended.emit("\n".join(active["evidence"]), info)
        elif active:
            log(f"session: ended ({reason}) بدونِ شواهد → پیشنهادی ارسال نشد")

    # --------- API برای اجرای دستی از رابطِ کاربری ---------
    def current_evidence(self):
        """کپیِ امنِ متنِ شواهدِ جمع‌شدهٔ فعلی (برای دکمهٔ پیشنهادِ دستی)."""
        with self._lock:
            if self._active and self._active["evidence"]:
                return "\n".join(self._active["evidence"])
        return ""

    def current_target(self):
        """(hwnd, name, ip) جلسهٔ فعال یا آخرین اتصالِ TCP (برای اجرای دستی)."""
        with self._lock:
            if self._active:
                return self._active.get("hwnd"), self._active.get("name"), self._active.get("ip")
        # اگر ناظر هنوز جلسه‌ای نساخته، از پنجره/اتصالِ فعلی حدس بزن
        try:
            sessions = detect_sessions(resolve=False)
            primary = sessions[0] if sessions else None
            ips = get_remote_connections(self.ports)
            hwnd = primary.get("hwnd") if primary else None
            name = primary.get("name") if primary else None
            ip = (primary.get("ip") if primary else None) or (ips[0] if ips else None)
            return hwnd, name, ip
        except Exception:
            return None, None, None

    def stop(self):
        self._stop = True
        self.wait(4000)

"""
ناظرِ جلسهٔ ریموت: «وصل/قطع» را از روی اتصالِ واقعیِ TCP (پورت‌های DameWare)
تشخیص می‌دهد. در طولِ اتصال هر چند ثانیه از پنجرهٔ ریموت عکس می‌گیرد، چند
«کی‌فریمِ» متمایز را نگه می‌دارد و متنشان را OCR می‌کند؛ به‌محضِ قطع، سیگنالِ
session_ended را با متنِ شواهد و مسیرِ کی‌فریم‌ها می‌فرستد تا صفحهٔ ثبت با
مدلِ تصویری (یا در نبودش با قواعد) پیشنهاد بسازد.

روی نخِ جدا اجرا می‌شود؛ همه‌چیز در session_ai.log لاگ می‌شود.
"""
import os
import time
import threading
from PySide6.QtCore import QThread, Signal

from services.remote_detector import detect_sessions, format_system_label, get_remote_connections
from services import session_ocr, screen_capture, task_inference
from services.debug_log import log

_MAX_LINES = 500
_MAX_FRAMES = 4
_POLL_SECONDS = 3


def build_suggestion(evidence, frames):
    """
    نتیجهٔ پیشنهاد را می‌سازد (اول مدلِ تصویری، اگر نبود قواعد). این تابع سنگین
    است (صدازدنِ مدل) پس باید خارج از نخِ UI صدا زده شود. یک نشستِ DB جدا باز
    می‌کند تا از نشستِ نخِ اصلی مستقل باشد.
    """
    from database.connection import SessionLocal
    from database.models import Task
    cfg = task_inference.load_config()
    session = SessionLocal()
    try:
        tasks = [(t.id, t.title) for t in session.query(Task).filter_by(is_active=True).all()]
    except Exception:
        tasks = []
    finally:
        session.close()

    result = None
    if frames:
        try:
            result = task_inference.infer_vision(frames, tasks, cfg)
        except Exception as e:
            log(f"suggestion: vision error: {e!r}")
            result = None
    if not result:
        try:
            result = task_inference.infer(evidence, tasks, cfg.get("rules"))
        except Exception as e:
            log(f"suggestion: rules error: {e!r}")
            result = None
    return result


def _safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


class InferenceThread(QThread):
    """اجرای دستیِ تحلیل (دکمهٔ «پیشنهاد از جلسهٔ فعلی») روی نخِ جدا."""
    done = Signal(object, dict)  # (result یا None, info)

    def __init__(self, evidence, frames, info, parent=None):
        super().__init__(parent)
        self._evidence = evidence
        self._frames = frames
        self._info = info

    def run(self):
        result = None
        try:
            result = build_suggestion(self._evidence, self._frames)
        except Exception as e:
            log(f"manual-infer error: {e!r}")
        for p in self._frames:
            _safe_remove(p)
        self.done.emit(result, self._info)


class SessionWatcher(QThread):
    # (نتیجهٔ پیشنهاد آماده, اطلاعاتِ سیستم) — هنگامِ پایانِ جلسه
    suggestion_ready = Signal(dict, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = task_inference.load_config()
        self.enabled = bool(cfg.get("enabled", True)) and screen_capture.is_supported()
        self.interval = max(3, int(cfg.get("interval_seconds", 8)))
        self.ports = cfg.get("dameware_ports") or None
        self._stop = False
        self._lock = threading.Lock()
        self._active = None

    def run(self):
        if not self.enabled:
            log("watcher: disabled")
            return
        log(f"watcher: started interval={self.interval}s ports={self.ports or 'default'}")
        while not self._stop:
            try:
                self._tick()
            except Exception as e:
                log(f"watcher: tick error: {e!r}")
            self._sleep(_POLL_SECONDS)
        # پاک‌سازیِ کی‌فریم‌های جلسهٔ ناتمام هنگام خروج
        self._discard_frames()
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
                                    "evidence": [], "seen": set(), "frames": [], "last": 0.0}
                log(f"session: started key={key} name={name} ip={ip} hwnd={hwnd}")
            elif hwnd:
                self._active["hwnd"] = hwnd
            now = time.time()
            if now - self._active["last"] >= self.interval:
                self._active["last"] = now
                self._capture()
        else:
            if self._active:
                self._finalize("disconnected")

    def _capture(self):
        hwnd = self._active.get("hwnd")
        path = screen_capture.capture_window(hwnd)
        if not path:
            return
        text = session_ocr.ocr_file(path)
        added = self._add_evidence(text)
        # کی‌فریم را فقط وقتی نگه دار که صفحه تغییرِ معنادار کرده (متنِ جدید)
        keep = added > 0 or not self._active["frames"]
        if keep:
            with self._lock:
                self._active["frames"].append(path)
                if len(self._active["frames"]) > _MAX_FRAMES:
                    old = self._active["frames"].pop(0)
                    self._safe_remove(old)
            log(f"capture: ocr_chars={len(text)} +{added} خط، فریم نگه‌داشته شد "
                f"(مجموع فریم={len(self._active['frames'])})")
        else:
            self._safe_remove(path)
            log(f"capture: ocr_chars={len(text)} تغییری نبود، فریم دور ریخته شد")

    def _add_evidence(self, text):
        if not text:
            return 0
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
        return added

    def _finalize(self, reason=""):
        with self._lock:
            active = self._active
            self._active = None
        if not active:
            return
        if active["evidence"] or active["frames"]:
            info = {
                "name": active["name"],
                "ip": active["ip"],
                "label": format_system_label(active["name"], active["ip"]),
            }
            log(f"session: ended ({reason}) خطوط={len(active['evidence'])} "
                f"فریم={len(active['frames'])} → تحلیل")
            # تحلیل روی همین نخِ ناظر (خارج از UI) انجام می‌شود.
            result = build_suggestion("\n".join(active["evidence"]), active["frames"])
            for p in active["frames"]:
                self._safe_remove(p)
            if result and (result.get("task_ids") or result.get("description")):
                log(f"session: پیشنهاد آماده source={result.get('source')} "
                    f"tasks={result.get('task_ids')}")
                self.suggestion_ready.emit(result, info)
            else:
                log("session: پیشنهادی حاصل نشد")
        else:
            log(f"session: ended ({reason}) بدونِ شواهد")

    @staticmethod
    def _safe_remove(path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    def _discard_frames(self):
        with self._lock:
            active = self._active
        if active:
            for p in active.get("frames", []):
                self._safe_remove(p)

    # --------- API برای اجرای دستی ---------
    def current_evidence(self):
        with self._lock:
            if self._active and self._active["evidence"]:
                return "\n".join(self._active["evidence"])
        return ""

    def current_frames(self):
        with self._lock:
            if self._active:
                return list(self._active.get("frames", []))
        return []

    def current_target(self):
        with self._lock:
            if self._active:
                return self._active.get("hwnd"), self._active.get("name"), self._active.get("ip")
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

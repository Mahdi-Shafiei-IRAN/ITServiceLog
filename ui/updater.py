"""اعلانِ نسخه‌ی جدید و نصبش از داخل برنامه.

چند ثانیه بعد از ورود و سپس هر دو ساعت، دیتابیس سرور را برای نسخه‌ی جدیدتر چک
می‌کند. با تأیید کاربر فایل نصبی دانلود و بررسی می‌شود، نصب‌کننده در حالت بی‌صدا اجرا
می‌شود و برنامه بسته می‌شود؛ نصب‌کننده بعد از پایان، برنامه را دوباره باز می‌کند.
فقط در نسخه‌ی نصب‌شده فعال است (نه هنگام اجرا از سورس).
"""
import os
import sys
import tempfile

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from database.connection import engine
from services import update_service

FIRST_CHECK_MS = 4000
CHECK_INTERVAL_MS = 2 * 60 * 60 * 1000
INSTALLER_ARGS = "/SILENT /SUPPRESSMSGBOXES /NORESTART /autoupdate=1"


class _Downloader(QThread):
    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, release, path):
        super().__init__()
        self.release, self.path = release, path

    def run(self):
        try:
            update_service.download(engine, self.release, self.path,
                                    lambda d, t: self.progress.emit(d, t))
            self.done.emit(self.path)
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateChecker(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._dismissed = set()   # نسخه‌هایی که کاربر «بعداً» زده (تا پایان همین اجرا)
        self._busy = False
        self._worker = None
        if not getattr(sys, "frozen", False):
            return
        QTimer.singleShot(FIRST_CHECK_MS, self.check)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check)
        self._timer.start(CHECK_INTERVAL_MS)

    def check(self):
        if self._busy:
            return
        try:
            rel = update_service.newer_release(engine)
        except Exception:
            return  # سرور در دسترس نیست؛ دفعه‌ی بعد
        if not rel or rel["version"] in self._dismissed:
            return
        self._busy = True
        try:
            if self._ask(rel):
                self._start_download(rel)
                return
            self._dismissed.add(rel["version"])
        finally:
            if self._worker is None:
                self._busy = False

    def _ask(self, rel):
        notes = (rel.get("notes") or "").strip()
        text = (f"نسخه‌ی جدید برنامه ({rel['version']}) آماده است. "
                f"نسخه‌ی فعلی شما: {update_service.current_version()}\n\n"
                + (f"تغییرات:\n{notes}\n\n" if notes else "")
                + "با «به‌روزرسانی»، برنامه بسته و نسخه‌ی جدید نصب می‌شود و دوباره باز می‌شود.\n"
                  "اگر اطلاعات ذخیره‌نشده دارید، اول «بعداً» را بزنید و ذخیره کنید.")
        box = QMessageBox(QMessageBox.Information, "به‌روزرسانی برنامه", text, parent=self.window)
        btn_update = box.addButton("به‌روزرسانی", QMessageBox.AcceptRole)
        box.addButton("بعداً", QMessageBox.RejectRole)
        box.setDefaultButton(btn_update)
        box.exec()
        return box.clickedButton() is btn_update

    def _start_download(self, rel):
        path = os.path.join(tempfile.gettempdir(), rel["file_name"])
        self._dialog = QProgressDialog("در حال دریافت نسخه‌ی جدید...", None, 0, 100, self.window)
        self._dialog.setWindowTitle("به‌روزرسانی برنامه")
        self._dialog.setWindowModality(Qt.WindowModal)
        self._dialog.setMinimumDuration(0)
        self._dialog.setAutoClose(False)
        self._dialog.setValue(0)
        self._worker = _Downloader(rel, path)
        self._worker.progress.connect(
            lambda d, t: self._dialog.setValue(int(d * 100 / t) if t else 0))
        self._worker.done.connect(self._install)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _finish_worker(self):
        self._dialog.close()
        self._worker.wait()
        self._worker = None
        self._busy = False

    def _failed(self, message):
        self._finish_worker()
        QMessageBox.warning(self.window, "به‌روزرسانی انجام نشد",
                            f"دریافت نسخه‌ی جدید ممکن نشد:\n{message}")

    def _install(self, path):
        self._finish_worker()
        try:
            # ShellExecute تا پنجره‌ی UAC (نصب در Program Files) نمایش داده شود
            os.startfile(path, "open", INSTALLER_ARGS)
        except OSError as exc:
            QMessageBox.warning(self.window, "به‌روزرسانی انجام نشد",
                                "نصب‌کننده اجرا نشد (شاید اجازه‌ی مدیر سیستم داده نشد).\n"
                                f"{exc}")
            return
        # برنامه بسته می‌شود تا نصب‌کننده بتواند فایل‌ها را جایگزین کند
        self.window.close()
        QApplication.quit()

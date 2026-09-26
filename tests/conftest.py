"""تنظیمات مشترک تست‌ها.

دیتابیس تست یک فایل SQLite موقت است (نه دیتابیس واقعی کاربر در APPDATA) و قبل از
import شدن database.connection از طریق ITSERVICELOG_DB تنظیم می‌شود.
Qt در حالت offscreen اجرا می‌شود تا تست‌های رابط کاربری بدون پنجره اجرا شوند.
"""
import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="itsl-tests-")
os.environ["ITSERVICELOG_DB"] = "sqlite:///" + os.path.join(_TMP_DIR, "test.sqlite").replace("\\", "/")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from database.connection import engine, SessionLocal  # noqa: E402
from database.models import Base, Technician  # noqa: E402


@pytest.fixture
def db():
    """هر تست با اسکیمای تازه و خالی شروع می‌شود."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_technician(db, full_name, username, role="Technician", can_log=False):
    tech = Technician(
        full_name=full_name,
        username=username,
        password_hash="x",
        role=role,
        department="BOTH" if role == "Administrator" else "IT",
        is_active=True,
        can_log_key_activities=can_log,
    )
    db.add(tech)
    db.commit()
    return tech


@pytest.fixture
def owner(db):
    return _make_technician(db, "مدیر IT", "manager", can_log=True)


@pytest.fixture
def other(db):
    return _make_technician(db, "کارشناس دیگر", "tech2")


@pytest.fixture
def admin(db):
    return _make_technician(db, "ادمین", "admin", role="Administrator")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setLayoutDirection(Qt.RightToLeft)
    return app


@pytest.fixture
def dialogs(monkeypatch):
    """جلوی باز شدن QMessageBox های مودال را می‌گیرد و پیام‌ها را ثبت می‌کند.

    خروجی: (calls, answers) — calls لیستی از (نوع, متن) است و
    answers["question"] پاسخِ پرسش‌های بله/خیر (پیش‌فرض: بله).
    """
    from PySide6.QtWidgets import QMessageBox
    calls = []
    answers = {"question": QMessageBox.Yes}

    def recorder(kind):
        def fake(*args, **kwargs):
            calls.append((kind, args[2] if len(args) > 2 else ""))
            return answers["question"] if kind == "question" else QMessageBox.Ok
        return fake

    for kind in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, kind, recorder(kind))
    return calls, answers

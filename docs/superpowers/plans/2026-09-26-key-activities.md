# IT Key Activities Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "کارهای شاخص IT" panel where permitted users log free-form key activities (one-day jobs or multi-week projects) with a progress timeline, plus a read-only admin report tab and a 3-sheet periodic Excel export.

**Architecture:** Two new SQLAlchemy tables (`key_activities`, `key_activity_updates`) plus one new boolean column on `technicians`. All business rules (period overlap, status transitions, summary numbers, filtering) live in a pure service module that both the Qt pages and the Excel exporter call. One Qt page class serves both modes (`admin=False` owner entry / `admin=True` read-only report).

**Tech Stack:** Python 3.12, PySide6 6.11, SQLAlchemy 2.1, openpyxl 3.1, pytest 9 (dev-only).

**Spec:** `docs/superpowers/specs/2026-09-26-key-activities-design.md`

## Global Constraints

- Work only on branch `feature/key-activities`. Never commit to `main`.
- No new runtime dependencies. `pytest` is dev-only and is NOT added to `requirements.txt`.
- Run tests with the project venv: `.venv/Scripts/python.exe -m pytest -q` (from the repo root, in Git Bash). Set `PYTHONIOENCODING=utf-8` if printing Persian text to the console.
- Shared files (`database/models.py`, `database/connection.py`, `ui/main_window.py`, `ui/technicians_page.py`) get only small, additive edits — a separate, unpushed v1.5 will be rebased onto this branch later. Do NOT refactor existing report pages (`site_reports_page.py`, `my_reports_page.py`, `admin_reports_page.py`, `named_services_page.py`).
- Schema changes are additive only: new tables via `Base.metadata.create_all`, new columns via `_NEW_COLUMNS` in `database/connection.py`. Boolean backfills use a bound parameter (`{"f": False}`), never the literal `0` (PostgreSQL rejects `boolean = integer`).
- Status values, exactly: `"برنامه‌ریزی"`, `"در حال انجام"`, `"انجام شد"`, `"متوقف"`, `"لغو شد"`.
- Priority values, exactly: `"عادی"`, `"مهم"`, `"خیلی مهم"`.
- Default categories, exactly: `"شبکه"`, `"سرور"`, `"امنیت"`, `"نرم‌افزار"`, `"سخت‌افزار"`, `"خرید و تأمین"`, `"آموزش"`, `"سایر"`.
- Tab titles, exactly: owner tab `"کارهای شاخص IT"`, admin tab `"گزارش کارهای شاخص"`.
- Excel sheet names, exactly: `"کارهای شاخص"`, `"گزارش پیشرفت"`, `"جمع‌بندی"`.
- Dates are displayed as `%Y/%m/%d` (Gregorian, like the rest of the app). Default export file name: `Key_Activities_YYYY-MM-DD_YYYY-MM-DD.xlsx`, or `Key_Activities_All.xlsx` when the period is "all time".
- A period `rng` is always either `None` (all time) or a tuple `(date_from, date_to)`, inclusive on both ends.
- Every DB commit in NEW code (dialog, page) is wrapped in `try/except` with `db.rollback()` and a clear Persian `QMessageBox`.
- Owner mode only ever queries/changes rows where `technician_id == technician.id`. Admin mode is read-only.
- Code style: match the surrounding code — Persian comments/docstrings, same naming and Qt idioms (`setObjectName("PageTitle")`, `setProperty("variant", "success"|"danger"|"ghost")`, `Qt.PointingHandCursor`).
- `ui.theme.theme.palette` is a **property** returning a dict (use `theme.palette["danger"]`, not `theme.palette()`).
- Commit messages: short imperative English, like existing history (e.g. "Add key activity models and migration"). No attribution trailers.

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `pytest.ini` | Create | pytest rootdir, `pythonpath = .`, `testpaths = tests` |
| `tests/conftest.py` | Create | Temp SQLite DB via `ITSERVICELOG_DB`, offscreen Qt, fixtures `db`, `owner`, `other`, `admin`, `qapp`, `dialogs` |
| `database/models.py` | Modify | Constants, `Technician.can_log_key_activities`, `KeyActivity`, `KeyActivityUpdate` |
| `database/connection.py` | Modify | `_NEW_COLUMNS` entry + backfill for the new column |
| `services/key_activity_service.py` | Create | Pure business logic (period, status, summary, filtering, validation, suggestions) |
| `reports/key_activities_exporter.py` | Create | 3-sheet Excel export + default file name |
| `ui/period_filter.py` | Create | `period_range()` pure function + `PeriodFilter` widget |
| `ui/key_activity_dialog.py` | Create | New/edit dialog |
| `ui/key_activities_page.py` | Create | Master-detail page (owner + admin modes) |
| `ui/main_window.py` | Modify | Add the two tabs |
| `ui/technicians_page.py` | Modify | "ثبت کارهای شاخص" checkbox + column |
| `version.txt`, `README.md` | Modify | `1.6.0`, feature + test docs |

---

### Task 1: Data model, migration, and test harness

**Files:**
- Create: `pytest.ini`, `tests/conftest.py`, `tests/test_key_activity_models.py`
- Modify: `database/models.py` (Technician class + append block at end of file)
- Modify: `database/connection.py` (`_NEW_COLUMNS` list and `_migrate()` backfill)

**Interfaces:**
- Produces (in `database/models.py`):
  - `KEY_STATUS_PLANNED, KEY_STATUS_IN_PROGRESS, KEY_STATUS_DONE, KEY_STATUS_ON_HOLD, KEY_STATUS_CANCELLED: str`, `KEY_STATUSES: list[str]`
  - `KEY_PRIORITY_NORMAL, KEY_PRIORITY_HIGH, KEY_PRIORITY_TOP: str`, `KEY_PRIORITIES: list[str]`
  - `KEY_CATEGORIES_DEFAULT: list[str]`
  - `Technician.can_log_key_activities: bool` (default `False`)
  - `KeyActivity` (table `key_activities`): `id, technician_id, technician_name_snapshot, title, category, priority, status, progress, start_date, end_date, description, result, created_at, updated_at`, relationships `technician`, `updates` (cascade `all, delete-orphan`)
  - `KeyActivityUpdate` (table `key_activity_updates`): `id, activity_id, update_date, text, progress, status, author_name_snapshot, created_at`, relationship `activity`
- Produces (in `tests/conftest.py`): fixtures `db` (fresh schema per test, yields a `Session`), `owner` (Technician with `can_log_key_activities=True`, full_name `"مدیر IT"`), `other` (plain Technician `"کارشناس دیگر"`), `admin` (Administrator `"ادمین"`), `qapp` (session-scoped `QApplication`), `dialogs` (monkeypatches `QMessageBox.information/warning/critical/question`; returns `(calls, answers)` where `calls` is a list of `(kind, text)` and `answers["question"]` is what `question` returns, default `QMessageBox.Yes`).

- [ ] **Step 1: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
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
```

- [ ] **Step 3: Write the failing model tests — `tests/test_key_activity_models.py`**

```python
from datetime import date

from sqlalchemy import create_engine, inspect, text

import database.connection as connection
from database.models import (Base, Technician, KeyActivity, KeyActivityUpdate,
                             KEY_STATUSES, KEY_PRIORITIES, KEY_CATEGORIES_DEFAULT,
                             KEY_STATUS_IN_PROGRESS, KEY_PRIORITY_NORMAL)


def test_constants_match_spec():
    assert KEY_STATUSES == ["برنامه‌ریزی", "در حال انجام", "انجام شد", "متوقف", "لغو شد"]
    assert KEY_PRIORITIES == ["عادی", "مهم", "خیلی مهم"]
    assert KEY_CATEGORIES_DEFAULT == ["شبکه", "سرور", "امنیت", "نرم‌افزار", "سخت‌افزار",
                                      "خرید و تأمین", "آموزش", "سایر"]


def test_technician_flag_defaults_to_false(db):
    tech = Technician(full_name="x", username="x", password_hash="x")
    db.add(tech)
    db.commit()
    assert tech.can_log_key_activities is False


def test_activity_defaults(db, owner):
    act = KeyActivity(technician_id=owner.id, title="راه‌اندازی سرور بکاپ")
    db.add(act)
    db.commit()
    assert act.priority == KEY_PRIORITY_NORMAL
    assert act.status == KEY_STATUS_IN_PROGRESS
    assert act.progress == 0
    assert act.start_date == date.today()
    assert act.end_date is None
    assert act.created_at is not None and act.updated_at is not None


def test_deleting_activity_deletes_its_updates(db, owner):
    act = KeyActivity(technician_id=owner.id, technician_name_snapshot=owner.full_name,
                      title="t", start_date=date(2026, 9, 1))
    act.updates.append(KeyActivityUpdate(update_date=date(2026, 9, 2), text="u1",
                                         author_name_snapshot=owner.full_name))
    db.add(act)
    db.commit()
    assert db.query(KeyActivityUpdate).count() == 1
    assert act.updates[0].activity is act

    db.delete(act)
    db.commit()
    assert db.query(KeyActivityUpdate).count() == 0


def test_migrate_adds_flag_column_to_old_database(tmp_path, monkeypatch):
    old = create_engine(f"sqlite:///{(tmp_path / 'old.sqlite').as_posix()}")
    with old.begin() as conn:
        conn.execute(text(
            "CREATE TABLE technicians (id INTEGER PRIMARY KEY, full_name VARCHAR(100) NOT NULL, "
            "internal_extension VARCHAR(20), username VARCHAR(50) NOT NULL UNIQUE, "
            "password_hash VARCHAR(128) NOT NULL, role VARCHAR(20), department VARCHAR(10), "
            "is_active BOOLEAN)"))
        conn.execute(text(
            "INSERT INTO technicians (full_name, username, password_hash, role, department, is_active) "
            "VALUES ('Old User', 'old', 'x', 'Technician', 'IT', 1)"))

    monkeypatch.setattr(connection, "engine", old)
    Base.metadata.create_all(bind=old)
    connection._migrate()

    insp = inspect(old)
    assert "can_log_key_activities" in {c["name"] for c in insp.get_columns("technicians")}
    assert {"key_activities", "key_activity_updates"} <= set(insp.get_table_names())
    with old.connect() as conn:
        rows = conn.execute(text("SELECT username, can_log_key_activities FROM technicians")).all()
    assert rows == [("old", 0)]
    old.dispose()
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activity_models.py -q`
Expected: collection error — `ImportError: cannot import name 'KeyActivity' from 'database.models'`

- [ ] **Step 5: Add the column to `Technician` in `database/models.py`**

Insert directly after the line `    is_active = Column(Boolean, default=True)` inside `class Technician` (the first `is_active` in the file, before `def departments(self):`):

```python
    # اجازه‌ی ثبت در تبِ «کارهای شاخص IT» (مستقل از نقش ادمین)
    can_log_key_activities = Column(Boolean, default=False)
```

- [ ] **Step 6: Append the key-activity block to the end of `database/models.py`**

```python


# ===========================================================================
# کارهای شاخص IT — کارهای آزاد (بدون فهرست خدمات از پیش تعریف‌شده)
# هر کار یک‌روزه یا پروژه‌ی چندهفته‌ای است و تاریخچه‌ی به‌روزرسانی دارد.
# ===========================================================================
KEY_STATUS_PLANNED = "برنامه‌ریزی"
KEY_STATUS_IN_PROGRESS = "در حال انجام"
KEY_STATUS_DONE = "انجام شد"
KEY_STATUS_ON_HOLD = "متوقف"
KEY_STATUS_CANCELLED = "لغو شد"
KEY_STATUSES = [KEY_STATUS_PLANNED, KEY_STATUS_IN_PROGRESS, KEY_STATUS_DONE,
                KEY_STATUS_ON_HOLD, KEY_STATUS_CANCELLED]

KEY_PRIORITY_NORMAL = "عادی"
KEY_PRIORITY_HIGH = "مهم"
KEY_PRIORITY_TOP = "خیلی مهم"
KEY_PRIORITIES = [KEY_PRIORITY_NORMAL, KEY_PRIORITY_HIGH, KEY_PRIORITY_TOP]

# فقط پیشنهاد است؛ کاربر هر دسته‌ی دیگری را هم می‌تواند تایپ کند
KEY_CATEGORIES_DEFAULT = ["شبکه", "سرور", "امنیت", "نرم‌افزار", "سخت‌افزار",
                          "خرید و تأمین", "آموزش", "سایر"]


class KeyActivity(Base):
    """یک «کار شاخص» که صاحبش آزادانه ثبت و در طول زمان به‌روز می‌کند."""
    __tablename__ = 'key_activities'
    id = Column(Integer, primary_key=True)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False, index=True)
    technician_name_snapshot = Column(String(100))

    title = Column(String(200), nullable=False)
    category = Column(String(50))                    # متن آزاد با پیشنهاد
    priority = Column(String(20), default=KEY_PRIORITY_NORMAL)
    status = Column(String(30), default=KEY_STATUS_IN_PROGRESS)
    progress = Column(Integer, default=0)            # ۰ تا ۱۰۰
    start_date = Column(Date, nullable=False, default=date.today, index=True)
    end_date = Column(Date, nullable=True)           # با «انجام شد» خودکار پر می‌شود
    description = Column(String(1000))               # شرح کار
    result = Column(String(1000))                    # نتیجه / دستاورد
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    technician = relationship("Technician")
    updates = relationship("KeyActivityUpdate", back_populates="activity",
                           cascade="all, delete-orphan")


class KeyActivityUpdate(Base):
    """یک به‌روزرسانی در خط زمانیِ یک کار شاخص (پیشرفت و وضعیت پس از آن)."""
    __tablename__ = 'key_activity_updates'
    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey('key_activities.id'), nullable=False, index=True)
    update_date = Column(Date, nullable=False, default=date.today, index=True)
    text = Column(String(1000), nullable=False)
    progress = Column(Integer)                       # درصد پیشرفت پس از این به‌روزرسانی
    status = Column(String(30))                      # وضعیت پس از این به‌روزرسانی
    author_name_snapshot = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)

    activity = relationship("KeyActivity", back_populates="updates")
```

- [ ] **Step 7: Register the migration in `database/connection.py`**

In `_NEW_COLUMNS`, after the line `    ("service_record_tasks", "note", "VARCHAR(300)"),` add:

```python
    ("technicians", "can_log_key_activities", "BOOLEAN"),
```

In `_migrate()`, inside the second `with engine.begin() as conn:` block, after the `("technicians", "department")` backfill (the `if ("technicians", "department") in added:` statement and its `conn.execute(...)`), add:

```python
        if ("technicians", "can_log_key_activities") in added:
            # پارامتر بولی (نه عدد ۰) تا روی PostgreSQL هم درست کار کند
            conn.execute(text(
                "UPDATE technicians SET can_log_key_activities = :f "
                "WHERE can_log_key_activities IS NULL"), {"f": False})
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activity_models.py -q`
Expected: `5 passed`

- [ ] **Step 9: Commit**

```bash
git add pytest.ini tests/conftest.py tests/test_key_activity_models.py database/models.py database/connection.py
git commit -m "Add key activity models, technician flag migration and test harness"
```

---

### Task 2: Business-logic service

**Files:**
- Create: `services/key_activity_service.py`
- Test: `tests/test_key_activity_service.py`

**Interfaces:**
- Consumes: models and constants from Task 1; fixtures `db`, `owner` from `tests/conftest.py`.
- Produces (module `services.key_activity_service`, imported elsewhere as `svc`):
  - `UNKNOWN = "نامشخص"`
  - `in_period(activity, rng) -> bool`
  - `updates_in_period(activities, rng) -> list[KeyActivityUpdate]` (ascending by `(update_date, id)`)
  - `summarize(activities, rng) -> dict` with keys `total, done_in_period, started_in_period, in_progress, updates_in_period` (ints) and `by_status, by_category, by_priority` (dict str→int)
  - `apply_status(activity, status, today) -> None`
  - `add_update(db, activity, update_date, text, progress=None, status=None, author="") -> KeyActivityUpdate` (raises `ValueError`; does NOT commit)
  - `validate_activity(title, start_date, end_date, progress) -> list[str]`
  - `category_suggestions(db) -> list[str]`
  - `last_update_date(activity) -> date | None`
  - `timeline(activity) -> list[KeyActivityUpdate]` (newest first)
  - `filter_activities(activities, rng=None, status=None, category=None, priority=None, owner_id=None, words=()) -> list[KeyActivity]`
  - `sort_activities(activities) -> list[KeyActivity]` (open first, then most recently updated)

- [ ] **Step 1: Write the failing tests — `tests/test_key_activity_service.py`**

```python
from datetime import date, datetime

import pytest

from database.models import (KeyActivity, KeyActivityUpdate, KEY_CATEGORIES_DEFAULT,
                             KEY_STATUS_DONE, KEY_STATUS_IN_PROGRESS, KEY_STATUS_ON_HOLD,
                             KEY_STATUS_CANCELLED, KEY_PRIORITY_NORMAL, KEY_PRIORITY_TOP)
from services import key_activity_service as svc

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def make(title="کار", start=date(2026, 9, 10), end=None, status=KEY_STATUS_IN_PROGRESS, **kw):
    return KeyActivity(title=title, start_date=start, end_date=end, status=status, **kw)


def dataset():
    a1 = make("A1", start=date(2026, 9, 5), end=date(2026, 9, 20), status=KEY_STATUS_DONE,
              category="شبکه", priority=KEY_PRIORITY_TOP, technician_id=1)
    a1.updates.append(KeyActivityUpdate(update_date=date(2026, 9, 20), text="تمام شد"))
    a2 = make("A2", start=date(2026, 8, 1), category="سرور", priority=KEY_PRIORITY_NORMAL,
              technician_id=2)
    a2.updates.append(KeyActivityUpdate(update_date=date(2026, 8, 15), text="شروع"))
    a2.updates.append(KeyActivityUpdate(update_date=date(2026, 9, 12), text="ادامه"))
    a3 = make("A3", start=date(2026, 9, 10), status=KEY_STATUS_ON_HOLD, category=None,
              priority=None, technician_id=2)
    a4 = make("A4", start=date(2026, 8, 1), end=date(2026, 8, 20), status=KEY_STATUS_DONE,
              category="شبکه", priority=KEY_PRIORITY_NORMAL, technician_id=2)
    a5 = make("A5", start=date(2026, 9, 25), category="شبکه", priority=KEY_PRIORITY_NORMAL,
              technician_id=2)
    return [a1, a2, a3, a4, a5]


# ------------------------------------------------------------------ in_period
def test_all_time_includes_everything():
    assert svc.in_period(make(start=date(2020, 1, 1)), None)


def test_open_activity_started_before_period_is_included():
    assert svc.in_period(make(start=date(2026, 8, 1)), SEPT)


def test_activity_started_after_period_is_excluded():
    assert not svc.in_period(make(start=date(2026, 10, 1)), SEPT)


def test_activity_finished_before_period_is_excluded():
    assert not svc.in_period(make(start=date(2026, 8, 1), end=date(2026, 8, 31)), SEPT)


def test_period_edges_are_inclusive():
    assert svc.in_period(make(start=date(2026, 9, 30)), SEPT)
    assert svc.in_period(make(start=date(2026, 8, 1), end=date(2026, 9, 1)), SEPT)


# ------------------------------------------------------------------ updates / summary
def test_updates_in_period_sorted_ascending():
    acts = dataset()
    ups = svc.updates_in_period(acts, SEPT)
    assert [u.text for u in ups] == ["ادامه", "تمام شد"]
    assert len(svc.updates_in_period(acts, None)) == 3


def test_summarize_period():
    s = svc.summarize(dataset(), SEPT)
    assert s["total"] == 4
    assert s["done_in_period"] == 1
    assert s["started_in_period"] == 3
    assert s["in_progress"] == 2
    assert s["updates_in_period"] == 2
    assert s["by_status"] == {KEY_STATUS_DONE: 1, KEY_STATUS_IN_PROGRESS: 2, KEY_STATUS_ON_HOLD: 1}
    assert s["by_category"] == {"شبکه": 2, "سرور": 1, svc.UNKNOWN: 1}
    assert s["by_priority"] == {KEY_PRIORITY_TOP: 1, KEY_PRIORITY_NORMAL: 2, svc.UNKNOWN: 1}


def test_summarize_all_time():
    s = svc.summarize(dataset(), None)
    assert s["total"] == 5
    assert s["done_in_period"] == 2
    assert s["started_in_period"] == 5
    assert s["in_progress"] == 2
    assert s["updates_in_period"] == 3


# ------------------------------------------------------------------ apply_status
def test_apply_done_sets_full_progress_and_end_date():
    act = make(progress=40)
    svc.apply_status(act, KEY_STATUS_DONE, date(2026, 9, 15))
    assert act.status == KEY_STATUS_DONE
    assert act.progress == 100
    assert act.end_date == date(2026, 9, 15)


def test_apply_done_keeps_existing_end_date():
    act = make(end=date(2026, 9, 12), progress=40)
    svc.apply_status(act, KEY_STATUS_DONE, date(2026, 9, 15))
    assert act.end_date == date(2026, 9, 12)


def test_leaving_done_clears_end_date_but_keeps_progress():
    act = make(end=date(2026, 9, 12), status=KEY_STATUS_DONE, progress=100)
    svc.apply_status(act, KEY_STATUS_IN_PROGRESS, date(2026, 9, 15))
    assert act.status == KEY_STATUS_IN_PROGRESS
    assert act.end_date is None
    assert act.progress == 100


def test_non_done_transition_keeps_manual_end_date():
    act = make(end=date(2026, 9, 30), status=KEY_STATUS_IN_PROGRESS)
    svc.apply_status(act, KEY_STATUS_ON_HOLD, date(2026, 9, 15))
    assert act.end_date == date(2026, 9, 30)


# ------------------------------------------------------------------ add_update
def _saved_activity(db, owner, **kw):
    kw.setdefault("start_date", date(2026, 9, 1))
    kw.setdefault("status", KEY_STATUS_IN_PROGRESS)
    kw.setdefault("progress", 10)
    act = KeyActivity(technician_id=owner.id, technician_name_snapshot=owner.full_name,
                      title="سرور بکاپ", **kw)
    db.add(act)
    db.commit()
    return act


def test_add_update_applies_progress(db, owner):
    act = _saved_activity(db, owner)
    before = act.updated_at
    upd = svc.add_update(db, act, date(2026, 9, 15), "  خرید استوریج  ", progress=40,
                         author=owner.full_name)
    db.commit()
    assert upd.text == "خرید استوریج"
    assert upd.author_name_snapshot == owner.full_name
    assert act.progress == 40
    assert act.status == KEY_STATUS_IN_PROGRESS
    assert act.end_date is None
    assert (upd.progress, upd.status) == (40, KEY_STATUS_IN_PROGRESS)
    assert len(act.updates) == 1
    assert act.updated_at >= before


def test_add_update_done_sets_end_date_and_full_progress(db, owner):
    act = _saved_activity(db, owner)
    upd = svc.add_update(db, act, date(2026, 9, 20), "تحویل شد", progress=80,
                         status=KEY_STATUS_DONE)
    db.commit()
    assert act.status == KEY_STATUS_DONE
    assert act.progress == 100
    assert act.end_date == date(2026, 9, 20)
    assert (upd.progress, upd.status) == (100, KEY_STATUS_DONE)


def test_add_update_same_status_does_not_touch_end_date(db, owner):
    act = _saved_activity(db, owner, status=KEY_STATUS_DONE, progress=100,
                          end_date=date(2026, 9, 5))
    svc.add_update(db, act, date(2026, 9, 20), "یادداشت پس از تحویل", status=KEY_STATUS_DONE)
    db.commit()
    assert act.end_date == date(2026, 9, 5)


@pytest.mark.parametrize("kwargs", [
    {"text": "   "},
    {"text": "ok", "progress": 101},
    {"text": "ok", "progress": -1},
    {"text": "ok", "status": "نامعتبر"},
])
def test_add_update_rejects_invalid_input(db, owner, kwargs):
    act = _saved_activity(db, owner)
    with pytest.raises(ValueError):
        svc.add_update(db, act, date(2026, 9, 15), **kwargs)
    assert act.updates == []


# ------------------------------------------------------------------ validation
def test_validate_activity_messages():
    assert svc.validate_activity("کار", date(2026, 9, 1), None, 0) == []
    assert svc.validate_activity("  ", date(2026, 9, 1), None, 0) == ["عنوان کار الزامی است."]
    assert svc.validate_activity("کار", None, None, 0) == ["تاریخ شروع الزامی است."]
    assert svc.validate_activity("کار", date(2026, 9, 10), date(2026, 9, 1), 0) == [
        "تاریخ اتمام نمی‌تواند قبل از تاریخ شروع باشد."]
    assert svc.validate_activity("کار", date(2026, 9, 1), None, 120) == [
        "درصد پیشرفت باید بین ۰ تا ۱۰۰ باشد."]


# ------------------------------------------------------------------ suggestions
def test_category_suggestions_defaults_then_used(db, owner):
    for cat in ["ذخیره‌سازی", "شبکه", "  ", None, "آنتی‌ویروس", "ذخیره‌سازی"]:
        db.add(KeyActivity(technician_id=owner.id, title="t", category=cat))
    db.commit()
    assert svc.category_suggestions(db) == KEY_CATEGORIES_DEFAULT + ["آنتی‌ویروس", "ذخیره‌سازی"]


# ------------------------------------------------------------------ helpers
def test_last_update_date_and_timeline():
    act = make()
    assert svc.last_update_date(act) is None
    for d in (date(2026, 9, 1), date(2026, 9, 15), date(2026, 9, 10)):
        act.updates.append(KeyActivityUpdate(update_date=d, text=str(d)))
    assert svc.last_update_date(act) == date(2026, 9, 15)
    assert [u.update_date for u in svc.timeline(act)] == [
        date(2026, 9, 15), date(2026, 9, 10), date(2026, 9, 1)]


def test_filter_activities():
    acts = dataset()
    titles = lambda xs: [a.title for a in xs]
    assert titles(svc.filter_activities(acts)) == ["A1", "A2", "A3", "A4", "A5"]
    assert titles(svc.filter_activities(acts, rng=SEPT)) == ["A1", "A2", "A3", "A5"]
    assert titles(svc.filter_activities(acts, status=KEY_STATUS_DONE)) == ["A1", "A4"]
    assert titles(svc.filter_activities(acts, category="شبکه")) == ["A1", "A4", "A5"]
    assert titles(svc.filter_activities(acts, priority=KEY_PRIORITY_TOP)) == ["A1"]
    assert titles(svc.filter_activities(acts, owner_id=1)) == ["A1"]
    assert titles(svc.filter_activities(acts, words=["ادامه"])) == ["A2"]   # متن به‌روزرسانی
    assert titles(svc.filter_activities(acts, words=["a1"])) == ["A1"]      # بی‌حساس به حروف


def test_sort_activities_open_first_then_recent():
    a = make("a", status=KEY_STATUS_DONE, updated_at=datetime(2026, 9, 20))
    b = make("b", updated_at=datetime(2026, 9, 1))
    c = make("c", updated_at=datetime(2026, 9, 15))
    d = make("d", status=KEY_STATUS_CANCELLED, updated_at=datetime(2026, 9, 25))
    assert [x.title for x in svc.sort_activities([a, b, c, d])] == ["c", "b", "d", "a"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activity_service.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'services.key_activity_service'`

- [ ] **Step 3: Implement `services/key_activity_service.py`**

```python
"""منطق کسب‌وکارِ «کارهای شاخص IT» — مستقل از رابط کاربری.

هم صفحه‌ها و هم خروجی اکسل از همین توابع استفاده می‌کنند تا عددها همیشه یکی باشند.
rng همه‌جا یا None (همه‌ی زمان‌ها) است یا تاپل (date_from, date_to) شاملِ دو سر.
"""
from datetime import datetime

from database.models import (KeyActivity, KeyActivityUpdate, KEY_STATUSES,
                             KEY_STATUS_DONE, KEY_STATUS_IN_PROGRESS, KEY_STATUS_CANCELLED,
                             KEY_CATEGORIES_DEFAULT)

UNKNOWN = "نامشخص"
_CLOSED = (KEY_STATUS_DONE, KEY_STATUS_CANCELLED)


def _in_range(d, rng):
    return rng is None or (d is not None and rng[0] <= d <= rng[1])


def in_period(activity, rng):
    """کار با بازه هم‌پوشانی دارد؟ کارِ باز (بدون تاریخ اتمام) تا امروز ادامه دارد."""
    if rng is None:
        return True
    if activity.start_date is None or activity.start_date > rng[1]:
        return False
    return activity.end_date is None or activity.end_date >= rng[0]


def updates_in_period(activities, rng):
    """به‌روزرسانی‌هایی که تاریخشان داخل بازه است (قدیمی به جدید)."""
    ups = [u for a in activities for u in a.updates if _in_range(u.update_date, rng)]
    return sorted(ups, key=lambda u: (u.update_date, u.id or 0))


def _count(values):
    out = {}
    for value in values:
        key = value or UNKNOWN
        out[key] = out.get(key, 0) + 1
    return out


def summarize(activities, rng):
    """عددهای نوار خلاصه و شیت جمع‌بندی (فقط روی کارهای داخل بازه)."""
    acts = [a for a in activities if in_period(a, rng)]
    return {
        "total": len(acts),
        "done_in_period": sum(1 for a in acts
                              if a.status == KEY_STATUS_DONE and _in_range(a.end_date, rng)),
        "started_in_period": sum(1 for a in acts if _in_range(a.start_date, rng)),
        "in_progress": sum(1 for a in acts if a.status == KEY_STATUS_IN_PROGRESS),
        "updates_in_period": len(updates_in_period(acts, rng)),
        "by_status": _count(a.status for a in acts),
        "by_category": _count(a.category for a in acts),
        "by_priority": _count(a.priority for a in acts),
    }


def apply_status(activity, status, today):
    """تغییر وضعیت با قاعده‌ی تاریخ اتمام.

    «انجام شد» ← پیشرفت ۱۰۰ و (اگر خالی بود) تاریخ اتمام = today.
    خروج از «انجام شد» ← تاریخ اتمام پاک می‌شود (پیشرفت دست نمی‌خورد).
    """
    was_done = activity.status == KEY_STATUS_DONE
    activity.status = status
    if status == KEY_STATUS_DONE:
        activity.progress = 100
        if activity.end_date is None:
            activity.end_date = today
    elif was_done:
        activity.end_date = None


def add_update(db, activity, update_date, text, progress=None, status=None, author=""):
    """یک به‌روزرسانی ثبت و پیشرفت/وضعیت کار را جلو می‌برد. commit نمی‌کند."""
    text = (text or "").strip()
    if not text:
        raise ValueError("متن به‌روزرسانی الزامی است.")
    if progress is not None and not 0 <= progress <= 100:
        raise ValueError("درصد پیشرفت باید بین ۰ تا ۱۰۰ باشد.")
    if status is not None and status not in KEY_STATUSES:
        raise ValueError(f"وضعیت نامعتبر است: {status}")

    if progress is not None:
        activity.progress = progress
    if status is not None and status != activity.status:
        apply_status(activity, status, update_date)
    activity.updated_at = datetime.now()

    update = KeyActivityUpdate(update_date=update_date, text=text,
                               progress=activity.progress, status=activity.status,
                               author_name_snapshot=author)
    activity.updates.append(update)
    db.add(update)
    return update


def validate_activity(title, start_date, end_date, progress):
    """پیام‌های خطای فرم کار شاخص (لیست خالی یعنی معتبر)."""
    errors = []
    if not (title or "").strip():
        errors.append("عنوان کار الزامی است.")
    if start_date is None:
        errors.append("تاریخ شروع الزامی است.")
    elif end_date is not None and end_date < start_date:
        errors.append("تاریخ اتمام نمی‌تواند قبل از تاریخ شروع باشد.")
    if progress is not None and not 0 <= progress <= 100:
        errors.append("درصد پیشرفت باید بین ۰ تا ۱۰۰ باشد.")
    return errors


def category_suggestions(db):
    """دسته‌های پیش‌فرض (به همان ترتیب) + دسته‌هایی که قبلاً ثبت شده‌اند (مرتب، بدون تکرار)."""
    out = list(KEY_CATEGORIES_DEFAULT)
    used = {(c or "").strip() for (c,) in db.query(KeyActivity.category).distinct()}
    out.extend(sorted(c for c in used if c and c not in out))
    return out


def last_update_date(activity):
    dates = [u.update_date for u in activity.updates if u.update_date]
    return max(dates) if dates else None


def timeline(activity):
    """به‌روزرسانی‌های یک کار، جدیدترین اول."""
    return sorted(activity.updates, key=lambda u: (u.update_date, u.id or 0), reverse=True)


def _search_text(activity):
    parts = [activity.title, activity.category, activity.description, activity.result,
             activity.technician_name_snapshot]
    parts += [u.text for u in activity.updates]
    return " ".join(p for p in parts if p).lower()


def filter_activities(activities, rng=None, status=None, category=None, priority=None,
                      owner_id=None, words=()):
    """فیلترهای صفحه؛ هر پارامتر None/خالی یعنی «همه»."""
    words = [w.lower() for w in words if w]
    out = []
    for a in activities:
        if not in_period(a, rng):
            continue
        if status and a.status != status:
            continue
        if category and (a.category or "") != category:
            continue
        if priority and a.priority != priority:
            continue
        if owner_id and a.technician_id != owner_id:
            continue
        if words:
            text = _search_text(a)
            if not all(w in text for w in words):
                continue
        out.append(a)
    return out


def sort_activities(activities):
    """کارهای باز اول، سپس بر اساس آخرین تغییر (جدیدترین اول)."""
    by_recent = sorted(activities, key=lambda a: a.updated_at or a.created_at or datetime.min,
                       reverse=True)
    return sorted(by_recent, key=lambda a: a.status in _CLOSED)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activity_service.py -q`
Expected: `24 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass (5 model tests + service tests).

- [ ] **Step 6: Commit**

```bash
git add services/key_activity_service.py tests/test_key_activity_service.py
git commit -m "Add key activity service: period, status, summary and filtering rules"
```

---

### Task 3: Excel exporter

**Files:**
- Create: `reports/key_activities_exporter.py`
- Test: `tests/test_key_activities_exporter.py`

**Interfaces:**
- Consumes: `svc.summarize`, `svc.updates_in_period` (Task 2); `_new_sheet(wb, title, headers, first=False)` and `_write_row(ws, row_num, values, wrap_from=1)` from `reports/excel_exporter.py` (existing).
- Produces:
  - `export_key_activities_to_excel(filepath, activities, rng, owner=None, show_owner=False) -> None`
  - `default_filename(rng) -> str`
  - `range_label(rng) -> str` (`"همه‌ی زمان‌ها"` or `"2026/09/01 تا 2026/09/30"`)

- [ ] **Step 1: Write the failing tests — `tests/test_key_activities_exporter.py`**

```python
from datetime import date

import openpyxl

from database.models import (KeyActivity, KeyActivityUpdate, Technician,
                             KEY_STATUS_DONE, KEY_STATUS_IN_PROGRESS,
                             KEY_PRIORITY_NORMAL, KEY_PRIORITY_TOP)
from reports.key_activities_exporter import (export_key_activities_to_excel,
                                             default_filename, range_label)

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def _acts():
    a1 = KeyActivity(title="راه‌اندازی سرور بکاپ", category="سرور", priority=KEY_PRIORITY_TOP,
                     status=KEY_STATUS_IN_PROGRESS, progress=60, start_date=date(2026, 8, 20),
                     technician_name_snapshot="مدیر IT", description="بکاپ شبانه", result=None)
    a1.updates.append(KeyActivityUpdate(update_date=date(2026, 8, 25), text="خرید استوریج",
                                        progress=20, status=KEY_STATUS_IN_PROGRESS,
                                        author_name_snapshot="مدیر IT"))
    a1.updates.append(KeyActivityUpdate(update_date=date(2026, 9, 10), text="نصب و پیکربندی",
                                        progress=60, status=KEY_STATUS_IN_PROGRESS,
                                        author_name_snapshot="مدیر IT"))
    a2 = KeyActivity(title="رفع قطعی شبکه", category="شبکه", priority=KEY_PRIORITY_NORMAL,
                     status=KEY_STATUS_DONE, progress=100, start_date=date(2026, 9, 5),
                     end_date=date(2026, 9, 5), technician_name_snapshot="مدیر IT")
    return [a1, a2]


def _summary(wb):
    ws = wb["جمع‌بندی"]
    return {ws.cell(row=r, column=1).value: ws.cell(row=r, column=2).value
            for r in range(2, ws.max_row + 1)}


def test_three_sheets_for_a_period(tmp_path):
    path = tmp_path / "k.xlsx"
    export_key_activities_to_excel(str(path), _acts(), SEPT)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["کارهای شاخص", "گزارش پیشرفت", "جمع‌بندی"]

    ws = wb["کارهای شاخص"]
    assert [c.value for c in ws[1]] == ["ردیف", "عنوان", "دسته", "اهمیت", "وضعیت",
                                        "پیشرفت ٪", "شروع", "اتمام", "شرح", "نتیجه"]
    assert ws.max_row == 3
    assert [c.value for c in ws[2]] == [1, "راه‌اندازی سرور بکاپ", "سرور", KEY_PRIORITY_TOP,
                                        KEY_STATUS_IN_PROGRESS, 60, "2026/08/20", "-",
                                        "بکاپ شبانه", "-"]

    ws2 = wb["گزارش پیشرفت"]
    assert [c.value for c in ws2[1]] == ["ردیف", "تاریخ", "عنوان کار", "متن به‌روزرسانی",
                                         "پیشرفت ٪", "وضعیت", "ثبت‌کننده"]
    assert ws2.max_row == 2   # فقط به‌روزرسانیِ داخل شهریور
    assert [c.value for c in ws2[2]] == [1, "2026/09/10", "راه‌اندازی سرور بکاپ",
                                         "نصب و پیکربندی", 60, KEY_STATUS_IN_PROGRESS, "مدیر IT"]

    summary = _summary(wb)
    assert summary["بازه‌ی گزارش"] == "2026/09/01 تا 2026/09/30"
    assert summary["تعداد کارهای شاخص در بازه"] == 2
    assert summary["انجام‌شده در بازه"] == 1
    assert summary["شروع‌شده در بازه"] == 1
    assert summary["در حال انجام"] == 1
    assert summary["تعداد به‌روزرسانی‌ها در بازه"] == 1
    assert summary["سرور"] == 1 and summary["شبکه"] == 1
    assert "ثبت‌کننده" not in summary


def test_owner_column_and_owner_row(tmp_path):
    path = tmp_path / "k.xlsx"
    owner = Technician(full_name="مدیر IT")
    export_key_activities_to_excel(str(path), _acts(), SEPT, owner=owner, show_owner=True)
    wb = openpyxl.load_workbook(path)
    headers = [c.value for c in wb["کارهای شاخص"][1]]
    assert headers[8] == "ثبت‌کننده"
    assert wb["کارهای شاخص"]["I2"].value == "مدیر IT"
    assert _summary(wb)["ثبت‌کننده"] == "مدیر IT"


def test_all_time_export(tmp_path):
    path = tmp_path / "k.xlsx"
    export_key_activities_to_excel(str(path), _acts(), None)
    wb = openpyxl.load_workbook(path)
    assert wb["گزارش پیشرفت"].max_row == 3
    assert _summary(wb)["بازه‌ی گزارش"] == "همه‌ی زمان‌ها"


def test_empty_export_still_has_three_sheets(tmp_path):
    path = tmp_path / "k.xlsx"
    export_key_activities_to_excel(str(path), [], SEPT)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["کارهای شاخص", "گزارش پیشرفت", "جمع‌بندی"]
    assert _summary(wb)["تعداد کارهای شاخص در بازه"] == 0


def test_default_filename_and_range_label():
    assert default_filename(SEPT) == "Key_Activities_2026-09-01_2026-09-30.xlsx"
    assert default_filename(None) == "Key_Activities_All.xlsx"
    assert range_label(None) == "همه‌ی زمان‌ها"
    assert range_label(SEPT) == "2026/09/01 تا 2026/09/30"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activities_exporter.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'reports.key_activities_exporter'`

- [ ] **Step 3: Implement `reports/key_activities_exporter.py`**

```python
"""خروجی اکسل «کارهای شاخص IT» — سه شیت، هم‌سبک با بقیه‌ی خروجی‌های برنامه.

  1. «کارهای شاخص»  — هر ردیف یک کار با وضعیت فعلی‌اش
  2. «گزارش پیشرفت» — فقط به‌روزرسانی‌های داخل بازه («در این بازه چه شد»)
  3. «جمع‌بندی»     — همان عددهای نوار خلاصه‌ی برنامه + تفکیک‌ها
"""
import openpyxl
from openpyxl.utils import get_column_letter

from reports.excel_exporter import _new_sheet, _write_row
from services import key_activity_service as svc


def _dt(d):
    return d.strftime("%Y/%m/%d") if d else "-"


def range_label(rng):
    return "همه‌ی زمان‌ها" if rng is None else f"{_dt(rng[0])} تا {_dt(rng[1])}"


def default_filename(rng):
    if rng is None:
        return "Key_Activities_All.xlsx"
    return f"Key_Activities_{rng[0]:%Y-%m-%d}_{rng[1]:%Y-%m-%d}.xlsx"


def export_key_activities_to_excel(filepath, activities, rng, owner=None, show_owner=False):
    wb = openpyxl.Workbook()

    # ---------------- شیت ۱: کارهای شاخص ----------------
    headers = ["ردیف", "عنوان", "دسته", "اهمیت", "وضعیت", "پیشرفت ٪", "شروع", "اتمام"]
    if show_owner:
        headers.append("ثبت‌کننده")
    headers += ["شرح", "نتیجه"]
    ws = _new_sheet(wb, "کارهای شاخص", headers, first=True)
    for i, a in enumerate(activities, 1):
        values = [i, a.title, a.category or "-", a.priority or "-", a.status or "-",
                  a.progress or 0, _dt(a.start_date), _dt(a.end_date)]
        if show_owner:
            values.append(a.technician_name_snapshot or "-")
        values += [a.description or "-", a.result or "-"]
        _write_row(ws, i + 1, values, wrap_from=2)
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["E"].width = 14
    if show_owner:
        ws.column_dimensions["I"].width = 18
    for col in (len(headers) - 1, len(headers)):  # شرح و نتیجه
        ws.column_dimensions[get_column_letter(col)].width = 45

    # ---------------- شیت ۲: گزارش پیشرفت ----------------
    ws2 = _new_sheet(wb, "گزارش پیشرفت", [
        "ردیف", "تاریخ", "عنوان کار", "متن به‌روزرسانی", "پیشرفت ٪", "وضعیت", "ثبت‌کننده",
    ])
    for i, u in enumerate(svc.updates_in_period(activities, rng), 1):
        _write_row(ws2, i + 1, [
            i,
            _dt(u.update_date),
            u.activity.title if u.activity else "-",
            u.text or "-",
            u.progress if u.progress is not None else "-",
            u.status or "-",
            u.author_name_snapshot or "-",
        ], wrap_from=3)
    ws2.column_dimensions["C"].width = 36
    ws2.column_dimensions["D"].width = 55
    ws2.column_dimensions["G"].width = 18

    # ---------------- شیت ۳: جمع‌بندی ----------------
    s = svc.summarize(activities, rng)
    rows = []
    if owner is not None:
        rows.append(("ثبت‌کننده", owner.full_name))
    rows.append(("بازه‌ی گزارش", range_label(rng)))
    rows += [
        ("تعداد کارهای شاخص در بازه", s["total"]),
        ("انجام‌شده در بازه", s["done_in_period"]),
        ("شروع‌شده در بازه", s["started_in_period"]),
        ("در حال انجام", s["in_progress"]),
        ("تعداد به‌روزرسانی‌ها در بازه", s["updates_in_period"]),
    ]
    for title, key in (("به تفکیک وضعیت", "by_status"),
                       ("به تفکیک دسته", "by_category"),
                       ("به تفکیک اهمیت", "by_priority")):
        rows.append(("", ""))
        rows.append((title, ""))
        rows.extend(sorted(s[key].items(), key=lambda kv: kv[1], reverse=True))
    ws3 = _new_sheet(wb, "جمع‌بندی", ["عنوان", "مقدار"])
    for i, (key, value) in enumerate(rows, 2):
        _write_row(ws3, i, [key, value], wrap_from=1)
    ws3.column_dimensions["A"].width = 40
    ws3.column_dimensions["B"].width = 24

    wb.save(filepath)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activities_exporter.py -q`
Expected: `5 passed`

- [ ] **Step 5: Run the whole suite, then commit**

Run: `.venv/Scripts/python.exe -m pytest -q` — Expected: all pass.

```bash
git add reports/key_activities_exporter.py tests/test_key_activities_exporter.py
git commit -m "Add three-sheet Excel export for key activities"
```

---

### Task 4: Period filter widget and key-activity dialog

**Files:**
- Create: `ui/period_filter.py`, `ui/key_activity_dialog.py`
- Test: `tests/test_period_filter.py`, `tests/test_key_activity_dialog.py`

**Interfaces:**
- Consumes: `svc.category_suggestions(db)`, `svc.validate_activity(...)` (Task 2); models/constants (Task 1); fixtures `qapp`, `db`, `owner`, `dialogs`.
- Produces:
  - `ui.period_filter.PERIODS: list[tuple[str, str]]`, `week_start(d) -> date`, `period_range(key, today, date_from=None, date_to=None) -> tuple[date, date] | None`
  - `ui.period_filter.PeriodFilter(default="this_month", parent=None)` — `QWidget` with signal `changed` (no args), methods `key() -> str`, `set_key(key) -> None`, `date_range() -> tuple | None`; attributes `combo`, `date_from`, `date_to`.
  - `ui.key_activity_dialog.KeyActivityDialog(db, technician, activity=None, parent=None)` — `QDialog`; attributes `txt_title, cmb_category, cmb_priority, cmb_status, spn_progress, date_start, chk_has_end, date_end, txt_description, txt_result, chk_one_day` (`chk_one_day` is `None` when editing); methods `values() -> dict`, `save() -> bool` (on success commits, sets `self.activity`, calls `accept()`).

- [ ] **Step 1: Write the failing period-filter tests — `tests/test_period_filter.py`**

```python
from datetime import date

from ui.period_filter import PeriodFilter, period_range, week_start

TODAY = date(2026, 9, 26)   # شنبه


def test_week_starts_on_saturday():
    assert week_start(date(2026, 9, 26)) == date(2026, 9, 26)   # شنبه
    assert week_start(date(2026, 10, 2)) == date(2026, 9, 26)   # جمعه
    assert week_start(date(2026, 9, 27)) == date(2026, 9, 26)   # یکشنبه


def test_period_ranges():
    assert period_range("all", TODAY) is None
    assert period_range("today", TODAY) == (TODAY, TODAY)
    assert period_range("yesterday", TODAY) == (date(2026, 9, 25), date(2026, 9, 25))
    assert period_range("last7", TODAY) == (date(2026, 9, 20), TODAY)
    assert period_range("last30", TODAY) == (date(2026, 8, 28), TODAY)
    assert period_range("this_week", TODAY) == (date(2026, 9, 26), TODAY)
    assert period_range("last_week", TODAY) == (date(2026, 9, 19), date(2026, 9, 25))
    assert period_range("this_month", TODAY) == (date(2026, 9, 1), TODAY)
    assert period_range("last_month", TODAY) == (date(2026, 8, 1), date(2026, 8, 31))


def test_custom_range_is_ordered():
    a, b = date(2026, 9, 10), date(2026, 9, 1)
    assert period_range("custom", TODAY, a, b) == (b, a)
    assert period_range("custom", TODAY, b, a) == (b, a)


def test_widget_default_and_custom_toggle(qapp):
    w = PeriodFilter(default="this_month")
    assert w.key() == "this_month"
    assert not w.date_from.isEnabled() and not w.date_to.isEnabled()
    fired = []
    w.changed.connect(lambda: fired.append(1))
    w.set_key("custom")
    assert w.date_from.isEnabled() and w.date_to.isEnabled()
    assert fired
    w.set_key("all")
    assert w.date_range() is None
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_period_filter.py -q`
Expected: `ModuleNotFoundError: No module named 'ui.period_filter'`

- [ ] **Step 3: Implement `ui/period_filter.py`**

```python
"""انتخاب بازه‌ی زمانی برای صفحه‌های «کارهای شاخص».

همان گزینه‌ها و همان تعریفِ «شروع هفته = شنبه» که صفحه‌های گزارش موجود دارند.
صفحه‌های قدیمی عمداً دست نخورده‌اند (منطق بازه‌شان تکراری است ولی refactor نشد).
"""
from datetime import date, timedelta

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QDateEdit
from PySide6.QtCore import QDate, Signal

PERIODS = [
    ("همه‌ی زمان‌ها", "all"), ("امروز", "today"), ("دیروز", "yesterday"),
    ("۷ روز اخیر", "last7"), ("این هفته", "this_week"), ("هفته‌ی گذشته", "last_week"),
    ("این ماه", "this_month"), ("ماه گذشته", "last_month"), ("۳۰ روز اخیر", "last30"),
    ("بازه‌ی دلخواه", "custom"),
]


def week_start(d):
    """شنبه‌ی همان هفته."""
    return d - timedelta(days=(d.weekday() - 5) % 7)


def period_range(key, today, date_from=None, date_to=None):
    """(از, تا) شاملِ دو سر، یا None برای «همه‌ی زمان‌ها»."""
    if key == "today":
        return today, today
    if key == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    if key == "last7":
        return today - timedelta(days=6), today
    if key == "last30":
        return today - timedelta(days=29), today
    if key == "this_week":
        return week_start(today), today
    if key == "last_week":
        ws = week_start(today) - timedelta(days=7)
        return ws, ws + timedelta(days=6)
    if key == "this_month":
        return today.replace(day=1), today
    if key == "last_month":
        last_prev = today.replace(day=1) - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if key == "custom" and date_from and date_to:
        return (date_from, date_to) if date_from <= date_to else (date_to, date_from)
    return None


class PeriodFilter(QWidget):
    """کشوییِ بازه + دو تاریخ از/تا (فقط در «بازه‌ی دلخواه» فعال)."""

    changed = Signal()

    def __init__(self, default="this_month", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.combo = QComboBox()
        for label, key in PERIODS:
            self.combo.addItem(label, key)
        self.date_from = self._date_edit(QDate.currentDate().addDays(-30))
        self.date_to = self._date_edit(QDate.currentDate())

        layout.addWidget(QLabel("بازه‌ی زمانی:"))
        layout.addWidget(self.combo)
        layout.addWidget(QLabel("از:"))
        layout.addWidget(self.date_from)
        layout.addWidget(QLabel("تا:"))
        layout.addWidget(self.date_to)

        self.set_key(default)
        self.combo.currentIndexChanged.connect(self._on_key_changed)

    def _date_edit(self, qdate):
        w = QDateEdit()
        w.setCalendarPopup(True)
        w.setDisplayFormat("yyyy/MM/dd")
        w.setDate(qdate)
        w.setEnabled(False)
        w.dateChanged.connect(lambda *_: self.changed.emit())
        return w

    def key(self):
        return self.combo.currentData()

    def set_key(self, key):
        idx = self.combo.findData(key)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self._sync_enabled()

    def _sync_enabled(self):
        custom = self.key() == "custom"
        self.date_from.setEnabled(custom)
        self.date_to.setEnabled(custom)

    def _on_key_changed(self, *_):
        self._sync_enabled()
        self.changed.emit()

    def date_range(self):
        return period_range(self.key(), date.today(),
                            self.date_from.date().toPython(), self.date_to.date().toPython())
```

- [ ] **Step 4: Run period-filter tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_period_filter.py -q`
Expected: `4 passed`

- [ ] **Step 5: Write the failing dialog tests — `tests/test_key_activity_dialog.py`**

```python
from datetime import date

from PySide6.QtCore import QDate

from database.models import (KeyActivity, KEY_STATUS_DONE, KEY_STATUS_IN_PROGRESS,
                             KEY_PRIORITY_NORMAL)
from ui.key_activity_dialog import KeyActivityDialog


def test_new_activity_is_saved_for_technician(qapp, db, owner, dialogs):
    dlg = KeyActivityDialog(db, owner)
    dlg.txt_title.setText("  راه‌اندازی سرور بکاپ ")
    dlg.cmb_category.setEditText("ذخیره‌سازی")
    dlg.txt_description.setPlainText("بکاپ شبانه‌ی سرورها")
    assert dlg.save() is True
    act = db.query(KeyActivity).one()
    assert act.title == "راه‌اندازی سرور بکاپ"
    assert act.category == "ذخیره‌سازی"
    assert act.description == "بکاپ شبانه‌ی سرورها"
    assert act.result is None
    assert act.technician_id == owner.id
    assert act.technician_name_snapshot == owner.full_name
    assert act.status == KEY_STATUS_IN_PROGRESS
    assert act.priority == KEY_PRIORITY_NORMAL
    assert act.progress == 0
    assert act.start_date == date.today()
    assert act.end_date is None
    assert dlg.activity is act


def test_blank_title_is_rejected(qapp, db, owner, dialogs):
    calls, _ = dialogs
    dlg = KeyActivityDialog(db, owner)
    assert dlg.save() is False
    assert db.query(KeyActivity).count() == 0
    assert calls and calls[0][0] == "warning" and "عنوان کار الزامی است." in calls[0][1]


def test_end_before_start_is_rejected(qapp, db, owner, dialogs):
    dlg = KeyActivityDialog(db, owner)
    dlg.txt_title.setText("کار")
    dlg.date_start.setDate(QDate(2026, 9, 10))
    dlg.chk_has_end.setChecked(True)
    dlg.date_end.setDate(QDate(2026, 9, 1))
    assert dlg.save() is False
    assert db.query(KeyActivity).count() == 0


def test_one_day_checkbox_marks_done_on_start_date(qapp, db, owner, dialogs):
    dlg = KeyActivityDialog(db, owner)
    dlg.txt_title.setText("رفع قطعی شبکه")
    dlg.date_start.setDate(QDate(2026, 9, 20))
    dlg.chk_one_day.setChecked(True)
    vals = dlg.values()
    assert vals["status"] == KEY_STATUS_DONE
    assert vals["progress"] == 100
    assert vals["end_date"] == date(2026, 9, 20)
    assert not dlg.cmb_status.isEnabled()
    dlg.date_start.setDate(QDate(2026, 9, 21))       # تاریخ اتمام دنبال شروع می‌آید
    assert dlg.values()["end_date"] == date(2026, 9, 21)
    dlg.chk_one_day.setChecked(False)
    assert dlg.cmb_status.isEnabled()


def test_switching_to_done_fills_end_date_and_back_clears_it(qapp, db, owner, dialogs):
    dlg = KeyActivityDialog(db, owner)
    dlg.cmb_status.setCurrentText(KEY_STATUS_DONE)
    assert dlg.chk_has_end.isChecked()
    assert dlg.date_end.date().toPython() == date.today()
    assert dlg.spn_progress.value() == 100
    dlg.cmb_status.setCurrentText(KEY_STATUS_IN_PROGRESS)
    assert not dlg.chk_has_end.isChecked()
    assert dlg.values()["end_date"] is None


def test_edit_existing_activity(qapp, db, owner, dialogs):
    act = KeyActivity(technician_id=owner.id, technician_name_snapshot=owner.full_name,
                      title="قدیمی", category="شبکه", start_date=date(2026, 9, 1),
                      status=KEY_STATUS_DONE, progress=100, end_date=date(2026, 9, 3))
    db.add(act)
    db.commit()
    dlg = KeyActivityDialog(db, owner, activity=act)
    assert dlg.chk_one_day is None
    assert dlg.txt_title.text() == "قدیمی"
    assert dlg.cmb_category.currentText() == "شبکه"
    assert dlg.chk_has_end.isChecked()
    assert dlg.date_end.date().toPython() == date(2026, 9, 3)
    dlg.txt_title.setText("جدید")
    assert dlg.save() is True
    db.refresh(act)
    assert act.title == "جدید"
    assert act.end_date == date(2026, 9, 3)
    assert db.query(KeyActivity).count() == 1


def test_category_combo_offers_defaults_and_used(qapp, db, owner, dialogs):
    db.add(KeyActivity(technician_id=owner.id, title="t", category="آنتی‌ویروس"))
    db.commit()
    dlg = KeyActivityDialog(db, owner)
    items = [dlg.cmb_category.itemText(i) for i in range(dlg.cmb_category.count())]
    assert items[0] == ""
    assert "شبکه" in items and "آنتی‌ویروس" in items
    assert dlg.cmb_category.isEditable()
```

- [ ] **Step 6: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activity_dialog.py -q`
Expected: `ModuleNotFoundError: No module named 'ui.key_activity_dialog'`

- [ ] **Step 7: Implement `ui/key_activity_dialog.py`**

```python
"""افزودن / ویرایش یک «کار شاخص IT»."""
from datetime import date, datetime

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
                               QComboBox, QSpinBox, QDateEdit, QCheckBox, QPlainTextEdit,
                               QPushButton, QMessageBox)
from PySide6.QtCore import Qt, QDate

from database.models import (KeyActivity, KEY_STATUSES, KEY_STATUS_DONE,
                             KEY_STATUS_IN_PROGRESS, KEY_PRIORITIES, KEY_PRIORITY_NORMAL)
from services import key_activity_service as svc


def _qdate(d):
    return QDate(d.year, d.month, d.day)


class KeyActivityDialog(QDialog):
    def __init__(self, db, technician, activity=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.technician = technician
        self.activity = activity
        self.setWindowTitle("ویرایش کار شاخص" if activity else "کار شاخص جدید")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(520)
        self._build()
        self._load()
        self._connect()

    # ------------------------------------------------------------------ UI
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("مثلاً: راه‌اندازی سرور بکاپ")
        form.addRow("عنوان:", self.txt_title)

        # «کار یک‌روزه» فقط برای کار جدید: یک ذخیره و تمام
        self.chk_one_day = None
        if self.activity is None:
            self.chk_one_day = QCheckBox("کار یک‌روزه — انجام شد")
            form.addRow("", self.chk_one_day)

        self.cmb_category = QComboBox()
        self.cmb_category.setEditable(True)  # دسته‌ی جدید هم قابل تایپ است
        self.cmb_category.addItem("")
        self.cmb_category.addItems(svc.category_suggestions(self.db))
        form.addRow("دسته:", self.cmb_category)

        self.cmb_priority = QComboBox()
        self.cmb_priority.addItems(KEY_PRIORITIES)
        form.addRow("اهمیت:", self.cmb_priority)

        self.cmb_status = QComboBox()
        self.cmb_status.addItems(KEY_STATUSES)
        form.addRow("وضعیت:", self.cmb_status)

        self.spn_progress = QSpinBox()
        self.spn_progress.setRange(0, 100)
        self.spn_progress.setSuffix(" ٪")
        form.addRow("پیشرفت:", self.spn_progress)

        self.date_start = self._date_edit()
        form.addRow("تاریخ شروع:", self.date_start)

        end_row = QHBoxLayout()
        self.chk_has_end = QCheckBox("تاریخ اتمام دارد")
        self.date_end = self._date_edit()
        end_row.addWidget(self.chk_has_end)
        end_row.addWidget(self.date_end, 1)
        form.addRow("تاریخ اتمام:", end_row)

        self.txt_description = QPlainTextEdit()
        self.txt_description.setPlaceholderText("شرح کار...")
        self.txt_description.setFixedHeight(80)
        form.addRow("شرح:", self.txt_description)

        self.txt_result = QPlainTextEdit()
        self.txt_result.setPlaceholderText("نتیجه / دستاورد (اختیاری)...")
        self.txt_result.setFixedHeight(80)
        form.addRow("نتیجه:", self.txt_result)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_save = QPushButton("ذخیره")
        btn_save.setProperty("variant", "success")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("انصراف")
        btn_cancel.setProperty("variant", "ghost")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _date_edit(self):
        w = QDateEdit()
        w.setCalendarPopup(True)
        w.setDisplayFormat("yyyy/MM/dd")
        w.setDate(QDate.currentDate())
        return w

    def _load(self):
        a = self.activity
        if a is None:
            self.cmb_priority.setCurrentText(KEY_PRIORITY_NORMAL)
            self.cmb_status.setCurrentText(KEY_STATUS_IN_PROGRESS)
        else:
            self.txt_title.setText(a.title or "")
            self.cmb_category.setCurrentText(a.category or "")
            self.cmb_priority.setCurrentText(a.priority or KEY_PRIORITY_NORMAL)
            self.cmb_status.setCurrentText(a.status or KEY_STATUS_IN_PROGRESS)
            self.spn_progress.setValue(a.progress or 0)
            if a.start_date:
                self.date_start.setDate(_qdate(a.start_date))
            if a.end_date:
                self.chk_has_end.setChecked(True)
                self.date_end.setDate(_qdate(a.end_date))
            self.txt_description.setPlainText(a.description or "")
            self.txt_result.setPlainText(a.result or "")
        self.date_end.setEnabled(self.chk_has_end.isChecked())
        self._last_status = self.cmb_status.currentText()

    def _connect(self):
        # بعد از بارگذاری وصل می‌شوند تا مقداردهی اولیه قاعده‌ها را اجرا نکند
        self.cmb_status.currentTextChanged.connect(self._on_status_changed)
        self.chk_has_end.toggled.connect(self._on_has_end)
        self.date_start.dateChanged.connect(self._on_start_changed)
        if self.chk_one_day is not None:
            self.chk_one_day.toggled.connect(self._on_one_day)

    # ------------------------------------------------------------ قاعده‌ها
    def _one_day(self):
        return self.chk_one_day is not None and self.chk_one_day.isChecked()

    def _on_status_changed(self, status):
        """همان قاعده‌ی apply_status در سرویس، روی فرم."""
        if status == KEY_STATUS_DONE:
            self.spn_progress.setValue(100)
            if not self.chk_has_end.isChecked():
                self.chk_has_end.setChecked(True)
                self.date_end.setDate(QDate.currentDate())
        elif self._last_status == KEY_STATUS_DONE:
            self.chk_has_end.setChecked(False)
        self._last_status = status

    def _on_has_end(self, checked):
        self.date_end.setEnabled(checked and not self._one_day())

    def _on_start_changed(self, *_):
        if self._one_day():
            self.date_end.setDate(self.date_start.date())

    def _on_one_day(self, checked):
        if checked:
            self.cmb_status.setCurrentText(KEY_STATUS_DONE)
            self.chk_has_end.setChecked(True)
            self.date_end.setDate(self.date_start.date())
        for w in (self.cmb_status, self.spn_progress, self.chk_has_end):
            w.setEnabled(not checked)
        self.date_end.setEnabled(self.chk_has_end.isChecked() and not checked)

    # ------------------------------------------------------------ ذخیره
    def values(self):
        status = self.cmb_status.currentText()
        progress = self.spn_progress.value()
        end = self.date_end.date().toPython() if self.chk_has_end.isChecked() else None
        if status == KEY_STATUS_DONE:  # همان قاعده‌ی apply_status
            progress = 100
            end = end or date.today()
        return {
            "title": self.txt_title.text().strip(),
            "category": self.cmb_category.currentText().strip() or None,
            "priority": self.cmb_priority.currentText(),
            "status": status,
            "progress": progress,
            "start_date": self.date_start.date().toPython(),
            "end_date": end,
            "description": self.txt_description.toPlainText().strip() or None,
            "result": self.txt_result.toPlainText().strip() or None,
        }

    def save(self):
        vals = self.values()
        errors = svc.validate_activity(vals["title"], vals["start_date"],
                                       vals["end_date"], vals["progress"])
        if errors:
            QMessageBox.warning(self, "خطا", "\n".join(errors))
            return False
        act = self.activity
        try:
            if act is None:
                act = KeyActivity(technician_id=self.technician.id,
                                  technician_name_snapshot=self.technician.full_name)
                self.db.add(act)
            for key, value in vals.items():
                setattr(act, key, value)
            act.updated_at = datetime.now()
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            QMessageBox.critical(self, "خطا", f"ذخیره‌ی کار شاخص ممکن نشد:\n{exc}")
            return False
        self.activity = act
        self.accept()
        return True
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_period_filter.py tests/test_key_activity_dialog.py -q`
Expected: `11 passed`

- [ ] **Step 9: Run the whole suite, then commit**

Run: `.venv/Scripts/python.exe -m pytest -q` — Expected: all pass.

```bash
git add ui/period_filter.py ui/key_activity_dialog.py tests/test_period_filter.py tests/test_key_activity_dialog.py
git commit -m "Add period filter widget and key activity dialog"
```

---

### Task 5: Key activities page (owner + admin modes)

**Files:**
- Create: `ui/key_activities_page.py`
- Test: `tests/test_key_activities_page.py`

**Interfaces:**
- Consumes: everything in `services.key_activity_service` (Task 2); `export_key_activities_to_excel`, `default_filename` (Task 3); `PeriodFilter` (`set_key`, `key`, `date_range`, signal `changed`) and `KeyActivityDialog` (`exec()`, `.activity`) (Task 4); `ui.theme.theme.palette` (property, dict); fixtures `qapp`, `db`, `owner`, `other`, `admin`, `dialogs`.
- Produces: `ui.key_activities_page.KeyActivitiesPage(db_session, technician, admin=False, parent=None)` with:
  - `load_data(select_id=None)` (called by `MainWindow.on_tab_changed` with no args)
  - attributes: `table`, `period`, `shown`, `current`, `stat_labels` (dict with keys `done_in_period, in_progress, started_in_period, updates_in_period` → `QLabel`), `lst_timeline`, `txt_search`, `cmb_status`, `cmb_category`, `cmb_priority`, `cmb_owner` (`None` in owner mode), `btn_new` / `update_box` (`None` in admin mode), and in owner mode `txt_update`, `spn_update_progress`, `cmb_update_status`, `date_update`, `btn_add_update`, `btn_edit`, `btn_delete`
  - methods `apply_filters(*_, select_id=None)`, `new_activity()`, `edit_activity()`, `add_update()`, `delete_activity()`, `export()`

- [ ] **Step 1: Write the failing tests — `tests/test_key_activities_page.py`**

```python
from datetime import date

from PySide6.QtWidgets import QFileDialog, QMessageBox

from database.models import (KeyActivity, KEY_STATUS_DONE, KEY_STATUS_IN_PROGRESS,
                             KEY_PRIORITY_TOP)
from ui.key_activities_page import KeyActivitiesPage


def _add(db, tech, title, **kw):
    kw.setdefault("start_date", date.today())
    kw.setdefault("status", KEY_STATUS_IN_PROGRESS)
    kw.setdefault("progress", 0)
    act = KeyActivity(technician_id=tech.id, technician_name_snapshot=tech.full_name,
                      title=title, **kw)
    db.add(act)
    db.commit()
    return act


def _page(db, tech, admin=False):
    page = KeyActivitiesPage(db, tech, admin=admin)
    page.period.set_key("all")
    return page


def test_default_period_is_this_month(qapp, db, owner, dialogs):
    assert KeyActivitiesPage(db, owner).period.key() == "this_month"


def test_owner_sees_only_own_activities(qapp, db, owner, other, dialogs):
    _add(db, owner, "A")
    _add(db, owner, "B")
    _add(db, other, "C")
    page = _page(db, owner)
    assert page.table.rowCount() == 2
    assert {a.title for a in page.shown} == {"A", "B"}
    assert page.btn_new is not None and page.update_box is not None
    assert page.cmb_owner is None


def test_admin_sees_all_read_only_with_owner_filter(qapp, db, owner, other, admin, dialogs):
    _add(db, owner, "A")
    _add(db, owner, "B")
    _add(db, other, "C")
    page = _page(db, admin, admin=True)
    assert page.table.rowCount() == 3
    assert page.btn_new is None and page.update_box is None
    page.cmb_owner.setCurrentIndex(page.cmb_owner.findData(other.id))
    assert [a.title for a in page.shown] == ["C"]


def test_selecting_a_row_shows_details(qapp, db, owner, dialogs):
    _add(db, owner, "سرور بکاپ", description="بکاپ شبانه")
    page = _page(db, owner)
    page.table.selectRow(0)
    assert page.current is not None and page.current.title == "سرور بکاپ"
    assert page.update_box.isEnabled()


def test_add_update_from_detail_panel(qapp, db, owner, dialogs):
    act = _add(db, owner, "سرور بکاپ", progress=10)
    page = _page(db, owner)
    page.table.selectRow(0)
    page.spn_update_progress.setValue(60)
    page.txt_update.setText("استوریج نصب شد")
    page.btn_add_update.click()
    db.refresh(act)
    assert act.progress == 60
    assert len(act.updates) == 1 and act.updates[0].text == "استوریج نصب شد"
    assert act.updates[0].author_name_snapshot == owner.full_name
    assert page.txt_update.text() == ""
    assert page.current is not None and page.current.id == act.id
    assert page.lst_timeline.count() == 1


def test_empty_update_text_is_rejected(qapp, db, owner, dialogs):
    calls, _ = dialogs
    act = _add(db, owner, "سرور بکاپ")
    page = _page(db, owner)
    page.table.selectRow(0)
    page.btn_add_update.click()
    db.refresh(act)
    assert act.updates == []
    assert calls[-1][0] == "warning"


def test_full_progress_offers_done_status(qapp, db, owner, dialogs):
    calls, answers = dialogs
    answers["question"] = QMessageBox.Yes
    act = _add(db, owner, "سرور بکاپ", progress=80)
    page = _page(db, owner)
    page.table.selectRow(0)
    page.spn_update_progress.setValue(100)
    page.txt_update.setText("تحویل شد")
    page.btn_add_update.click()
    db.refresh(act)
    assert any(kind == "question" for kind, _ in calls)
    assert act.status == KEY_STATUS_DONE
    assert act.end_date == date.today()


def test_full_progress_declined_keeps_status(qapp, db, owner, dialogs):
    _, answers = dialogs
    answers["question"] = QMessageBox.No
    act = _add(db, owner, "سرور بکاپ", progress=80)
    page = _page(db, owner)
    page.table.selectRow(0)
    page.spn_update_progress.setValue(100)
    page.txt_update.setText("تقریباً تمام")
    page.btn_add_update.click()
    db.refresh(act)
    assert act.progress == 100
    assert act.status == KEY_STATUS_IN_PROGRESS


def test_summary_strip_counts(qapp, db, owner, dialogs):
    _add(db, owner, "done", status=KEY_STATUS_DONE, progress=100, end_date=date.today())
    _add(db, owner, "open")
    page = _page(db, owner)
    assert page.stat_labels["done_in_period"].text() == "1"
    assert page.stat_labels["in_progress"].text() == "1"
    assert page.stat_labels["started_in_period"].text() == "2"
    assert page.stat_labels["updates_in_period"].text() == "0"


def test_filters_and_search(qapp, db, owner, dialogs):
    _add(db, owner, "رفع قطعی شبکه", category="شبکه", priority=KEY_PRIORITY_TOP)
    _add(db, owner, "خرید لایسنس", category="نرم‌افزار")
    page = _page(db, owner)
    page.cmb_category.setCurrentIndex(page.cmb_category.findData("شبکه"))
    assert [a.title for a in page.shown] == ["رفع قطعی شبکه"]
    page.cmb_category.setCurrentIndex(0)
    page.txt_search.setText("لایسنس")
    assert [a.title for a in page.shown] == ["خرید لایسنس"]


def test_delete_activity_with_confirmation(qapp, db, owner, dialogs):
    _add(db, owner, "حذفی")
    page = _page(db, owner)
    page.table.selectRow(0)
    page.btn_delete.click()
    assert db.query(KeyActivity).count() == 0
    assert page.table.rowCount() == 0
    assert page.current is None


def test_delete_cancelled_keeps_activity(qapp, db, owner, dialogs):
    _, answers = dialogs
    answers["question"] = QMessageBox.No
    _add(db, owner, "بماند")
    page = _page(db, owner)
    page.table.selectRow(0)
    page.btn_delete.click()
    assert db.query(KeyActivity).count() == 1


def test_export_writes_file(qapp, db, owner, dialogs, monkeypatch, tmp_path):
    _add(db, owner, "A")
    target = tmp_path / "out.xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    page = _page(db, owner)
    page.export()
    assert target.exists()


def test_export_with_nothing_shown_warns(qapp, db, owner, dialogs):
    calls, _ = dialogs
    page = _page(db, owner)
    page.export()
    assert calls[-1][0] == "warning"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activities_page.py -q`
Expected: `ModuleNotFoundError: No module named 'ui.key_activities_page'`

- [ ] **Step 3: Implement `ui/key_activities_page.py`**

```python
"""«کارهای شاخص IT» — پنل ثبت (صاحب کار) و تب گزارش (ادمین).

  • admin=False: فقط کارهای همان کاربر؛ افزودن، ویرایش، حذف و ثبت به‌روزرسانی.
  • admin=True : کارهای همه‌ی کاربران + فیلتر «ثبت‌کننده»؛ فقط‌خواندنی.
هر دو حالت نوار خلاصه‌ی بازه و خروجی اکسل دارند. همه‌ی عددها از
services.key_activity_service می‌آیند تا با فایل اکسل یکی باشند.
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QSplitter, QFrame,
                               QListWidget, QSpinBox, QDateEdit, QMessageBox, QFileDialog,
                               QProgressBar)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QDate

from database.models import (KeyActivity, Technician, KEY_STATUSES, KEY_STATUS_DONE,
                             KEY_STATUS_IN_PROGRESS, KEY_PRIORITIES, KEY_PRIORITY_TOP)
from reports.key_activities_exporter import export_key_activities_to_excel, default_filename
from services import key_activity_service as svc
from ui.key_activity_dialog import KeyActivityDialog
from ui.period_filter import PeriodFilter
from ui.theme import theme

_STATS = [
    ("done_in_period", "انجام‌شده در بازه"),
    ("in_progress", "در حال انجام"),
    ("started_in_period", "شروع‌شده در بازه"),
    ("updates_in_period", "به‌روزرسانی‌ها"),
]


def _dt(d):
    return d.strftime("%Y/%m/%d") if d else "-"


class KeyActivitiesPage(QWidget):
    def __init__(self, db_session, technician, admin=False, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.technician = technician
        self.admin = admin
        self.all = []
        self.shown = []
        self.current = None
        self.btn_new = None
        self.update_box = None
        self.cmb_owner = None
        self.setup_ui()
        self.load_data()

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("گزارش کارهای شاخص" if self.admin else "کارهای شاخص IT")
        title.setObjectName("PageTitle")
        head.addWidget(title)
        head.addStretch()
        if not self.admin:
            self.btn_new = QPushButton("+ کار شاخص جدید")
            self.btn_new.setProperty("variant", "success")
            self.btn_new.setCursor(Qt.PointingHandCursor)
            self.btn_new.clicked.connect(self.new_activity)
            head.addWidget(self.btn_new)
        layout.addLayout(head)

        # نوار خلاصه‌ی بازه (همان عددهای شیت «جمع‌بندی»)
        strip = QHBoxLayout()
        self.stat_labels = {}
        for key, caption in _STATS:
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            value = QLabel("0")
            value.setObjectName("SectionTitle")
            cap = QLabel(caption)
            cap.setObjectName("Muted")
            card_layout.addWidget(value)
            card_layout.addWidget(cap)
            self.stat_labels[key] = value
            strip.addWidget(card)
        layout.addLayout(strip)

        bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو در عنوان، شرح، نتیجه و به‌روزرسانی‌ها...")
        self.txt_search.textChanged.connect(self.apply_filters)
        bar.addWidget(QLabel("جستجو:"))
        bar.addWidget(self.txt_search, 2)
        self.cmb_status = self._filter_combo("همه‌ی وضعیت‌ها", KEY_STATUSES)
        self.cmb_category = self._filter_combo("همه‌ی دسته‌ها", [])
        self.cmb_priority = self._filter_combo("همه‌ی اهمیت‌ها", KEY_PRIORITIES)
        bar.addWidget(QLabel("وضعیت:"))
        bar.addWidget(self.cmb_status, 1)
        bar.addWidget(QLabel("دسته:"))
        bar.addWidget(self.cmb_category, 1)
        bar.addWidget(QLabel("اهمیت:"))
        bar.addWidget(self.cmb_priority, 1)
        if self.admin:
            self.cmb_owner = self._filter_combo("همه‌ی ثبت‌کننده‌ها", [])
            bar.addWidget(QLabel("ثبت‌کننده:"))
            bar.addWidget(self.cmb_owner, 1)
        layout.addLayout(bar)

        bar2 = QHBoxLayout()
        self.period = PeriodFilter(default="this_month")
        self.period.changed.connect(self.apply_filters)
        bar2.addWidget(self.period)
        bar2.addStretch()
        btn_refresh = QPushButton("بروزرسانی")
        btn_refresh.setProperty("variant", "ghost")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(lambda: self.load_data())
        btn_export = QPushButton("خروجی اکسل")
        btn_export.setProperty("variant", "success")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self.export)
        bar2.addWidget(btn_refresh)
        bar2.addWidget(btn_export)
        layout.addLayout(bar2)

        splitter = QSplitter(Qt.Horizontal)
        headers = self._headers()
        self._progress_col = headers.index("پیشرفت")
        self._priority_col = headers.index("اهمیت")
        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for i in range(len(headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection)
        if not self.admin:
            self.table.doubleClicked.connect(lambda *_: self.edit_activity())
        splitter.addWidget(self.table)
        splitter.addWidget(self._build_detail())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("Muted")
        layout.addWidget(self.lbl_count)

    def _filter_combo(self, all_label, options):
        cmb = QComboBox()
        cmb.addItem(all_label, None)
        for opt in options:
            cmb.addItem(opt, opt)
        cmb.currentIndexChanged.connect(self.apply_filters)
        return cmb

    def _headers(self):
        cols = ["عنوان"]
        if self.admin:
            cols.append("ثبت‌کننده")
        return cols + ["دسته", "اهمیت", "وضعیت", "پیشرفت", "شروع", "آخرین به‌روزرسانی"]

    def _build_detail(self):
        panel = QFrame()
        panel.setObjectName("Card")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        self.lbl_title = QLabel("")
        self.lbl_title.setObjectName("SectionTitle")
        self.lbl_title.setWordWrap(True)
        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("Muted")
        self.lbl_meta.setWordWrap(True)
        self.lbl_description = QLabel("")
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_result = QLabel("")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        for w in (self.lbl_title, self.lbl_meta, self.lbl_description, self.lbl_result):
            lay.addWidget(w)

        timeline_title = QLabel("تاریخچه‌ی به‌روزرسانی‌ها")
        timeline_title.setObjectName("SectionTitle")
        lay.addWidget(timeline_title)
        self.lst_timeline = QListWidget()
        self.lst_timeline.setWordWrap(True)
        lay.addWidget(self.lst_timeline, 1)

        if not self.admin:
            self.update_box = QFrame()
            ul = QVBoxLayout(self.update_box)
            ul.setContentsMargins(0, 0, 0, 0)
            ul.setSpacing(6)
            row = QHBoxLayout()
            self.date_update = QDateEdit()
            self.date_update.setCalendarPopup(True)
            self.date_update.setDisplayFormat("yyyy/MM/dd")
            self.date_update.setDate(QDate.currentDate())
            self.spn_update_progress = QSpinBox()
            self.spn_update_progress.setRange(0, 100)
            self.spn_update_progress.setSuffix(" ٪")
            self.cmb_update_status = QComboBox()
            self.cmb_update_status.addItems(KEY_STATUSES)
            row.addWidget(QLabel("تاریخ:"))
            row.addWidget(self.date_update)
            row.addWidget(QLabel("پیشرفت:"))
            row.addWidget(self.spn_update_progress)
            row.addWidget(QLabel("وضعیت:"))
            row.addWidget(self.cmb_update_status, 1)
            ul.addLayout(row)
            self.txt_update = QLineEdit()
            self.txt_update.setPlaceholderText("چه کاری انجام شد؟ (مثلاً: استوریج خریداری و نصب شد)")
            ul.addWidget(self.txt_update)
            self.btn_add_update = QPushButton("ثبت به‌روزرسانی")
            self.btn_add_update.setCursor(Qt.PointingHandCursor)
            self.btn_add_update.clicked.connect(self.add_update)
            ul.addWidget(self.btn_add_update)
            lay.addWidget(self.update_box)

            actions = QHBoxLayout()
            self.btn_edit = QPushButton("ویرایش")
            self.btn_edit.setProperty("variant", "ghost")
            self.btn_edit.setCursor(Qt.PointingHandCursor)
            self.btn_edit.clicked.connect(self.edit_activity)
            self.btn_delete = QPushButton("حذف")
            self.btn_delete.setProperty("variant", "danger")
            self.btn_delete.setCursor(Qt.PointingHandCursor)
            self.btn_delete.clicked.connect(self.delete_activity)
            actions.addStretch()
            actions.addWidget(self.btn_edit)
            actions.addWidget(self.btn_delete)
            lay.addLayout(actions)

        self._show_detail(None)
        return panel

    # ------------------------------------------------------------ داده‌ها
    def load_data(self, select_id=None):
        if select_id is None and self.current is not None:
            select_id = self.current.id
        self._refresh_combo(self.cmb_category,
                            [(c, c) for c in svc.category_suggestions(self.db)])
        query = self.db.query(KeyActivity)
        if self.admin:
            owner_ids = {tid for (tid,) in self.db.query(KeyActivity.technician_id).distinct()}
            techs = self.db.query(Technician).order_by(Technician.full_name).all()
            self._refresh_combo(self.cmb_owner, [(t.full_name, t.id) for t in techs
                                                 if t.can_log_key_activities or t.id in owner_ids])
        else:
            query = query.filter(KeyActivity.technician_id == self.technician.id)
        self.all = query.all()
        self.apply_filters(select_id=select_id)

    def _refresh_combo(self, combo, items):
        """گزینه‌ها را تازه می‌کند (به‌جز «همه») و انتخاب فعلی را حفظ می‌کند."""
        current = combo.currentData()
        combo.blockSignals(True)
        while combo.count() > 1:
            combo.removeItem(1)
        for label, data in items:
            combo.addItem(label, data)
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def apply_filters(self, *_, select_id=None):
        if select_id is None and self.current is not None:
            select_id = self.current.id
        rng = self.period.date_range()
        filtered = svc.filter_activities(
            self.all, rng=rng,
            status=self.cmb_status.currentData(),
            category=self.cmb_category.currentData(),
            priority=self.cmb_priority.currentData(),
            owner_id=self.cmb_owner.currentData() if self.cmb_owner is not None else None,
            words=self.txt_search.text().split())
        self.shown = svc.sort_activities(filtered)
        self._fill_table()
        summary = svc.summarize(self.shown, rng)
        for key, label in self.stat_labels.items():
            label.setText(str(summary[key]))
        self._select(select_id)

    def _fill_table(self):
        t = self.table
        t.blockSignals(True)
        t.clearSelection()
        t.setRowCount(len(self.shown))
        danger = QColor(theme.palette["danger"])
        for row, a in enumerate(self.shown):
            values = [a.title]
            if self.admin:
                values.append(a.technician_name_snapshot or "-")
            values += [a.category or "-", a.priority or "-", a.status or "-", "",
                       _dt(a.start_date), _dt(svc.last_update_date(a))]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment((Qt.AlignRight if col == 0 else Qt.AlignCenter)
                                      | Qt.AlignVCenter)
                if a.priority == KEY_PRIORITY_TOP:
                    if col == 0:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    elif col == self._priority_col:
                        item.setForeground(danger)
                t.setItem(row, col, item)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(a.progress or 0)
            bar.setFormat("%p٪")
            bar.setAlignment(Qt.AlignCenter)
            t.setCellWidget(row, self._progress_col, bar)
        t.blockSignals(False)
        self.lbl_count.setText(f"تعداد کارهای نمایش‌داده‌شده: {len(self.shown)}")

    def _select(self, select_id):
        row = -1
        if select_id is not None:
            row = next((i for i, a in enumerate(self.shown) if a.id == select_id), -1)
        if row >= 0:
            self.table.selectRow(row)
        else:
            self.current = None
            self._show_detail(None)

    def _on_selection(self):
        rows = self.table.selectionModel().selectedRows()
        row = rows[0].row() if rows else -1
        self.current = self.shown[row] if 0 <= row < len(self.shown) else None
        self._show_detail(self.current)

    def _show_detail(self, a):
        self.lst_timeline.clear()
        if a is None:
            self.lbl_title.setText("یک کار را از فهرست انتخاب کنید.")
            for w in (self.lbl_meta, self.lbl_description, self.lbl_result):
                w.setText("")
            self._set_detail_enabled(False)
            return
        self.lbl_title.setText(a.title)
        meta = [f"دسته: {a.category or '-'}", f"اهمیت: {a.priority or '-'}",
                f"وضعیت: {a.status or '-'}", f"پیشرفت: {a.progress or 0}٪",
                f"شروع: {_dt(a.start_date)}", f"اتمام: {_dt(a.end_date)}"]
        if self.admin:
            meta.insert(0, f"ثبت‌کننده: {a.technician_name_snapshot or '-'}")
        self.lbl_meta.setText("  •  ".join(meta))
        self.lbl_description.setText(f"شرح: {a.description or '-'}")
        self.lbl_result.setText(f"نتیجه: {a.result or '-'}")
        for u in svc.timeline(a):
            progress = f"{u.progress}٪" if u.progress is not None else "-"
            self.lst_timeline.addItem(
                f"{_dt(u.update_date)}  —  {progress}  —  {u.status or '-'}\n{u.text}")
        if not a.updates:
            self.lst_timeline.addItem("هنوز به‌روزرسانی‌ای ثبت نشده است.")
        if not self.admin:
            self.spn_update_progress.setValue(a.progress or 0)
            self.cmb_update_status.setCurrentText(a.status or KEY_STATUS_IN_PROGRESS)
            self.date_update.setDate(QDate.currentDate())
            self._set_detail_enabled(True)

    def _set_detail_enabled(self, enabled):
        if self.admin:
            return
        for w in (self.update_box, self.btn_edit, self.btn_delete):
            w.setEnabled(enabled)

    # ------------------------------------------------------------ عملیات
    def new_activity(self):
        if self.admin:
            return
        dlg = KeyActivityDialog(self.db, self.technician, parent=self)
        if dlg.exec():
            self.load_data(select_id=dlg.activity.id)

    def edit_activity(self):
        if self.admin or self.current is None:
            return
        dlg = KeyActivityDialog(self.db, self.technician, activity=self.current, parent=self)
        if dlg.exec():
            self.load_data()

    def add_update(self):
        if self.admin or self.current is None:
            return
        text = self.txt_update.text().strip()
        if not text:
            QMessageBox.warning(self, "خطا", "متن به‌روزرسانی را وارد کنید.")
            return
        progress = self.spn_update_progress.value()
        status = self.cmb_update_status.currentText()
        if progress == 100 and status != KEY_STATUS_DONE:
            answer = QMessageBox.question(
                self, "تکمیل کار",
                "پیشرفت به ۱۰۰٪ رسید. وضعیت هم به «انجام شد» تغییر کند؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                status = KEY_STATUS_DONE
        try:
            svc.add_update(self.db, self.current, self.date_update.date().toPython(), text,
                           progress=progress, status=status, author=self.technician.full_name)
            self.db.commit()
        except ValueError as exc:
            self.db.rollback()
            QMessageBox.warning(self, "خطا", str(exc))
            return
        except Exception as exc:
            self.db.rollback()
            QMessageBox.critical(self, "خطا", f"ثبت به‌روزرسانی ممکن نشد:\n{exc}")
            return
        self.txt_update.clear()
        self.load_data()

    def delete_activity(self):
        if self.admin or self.current is None:
            return
        a = self.current
        confirm = QMessageBox.question(
            self, "تأیید حذف",
            f"کار شاخص «{a.title}» همراه با {len(a.updates)} به‌روزرسانی حذف شود؟ "
            "این عملیات قابل بازگشت نیست.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        try:
            self.db.delete(a)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            QMessageBox.critical(self, "خطا", f"حذف کار شاخص ممکن نشد:\n{exc}")
            return
        self.current = None
        self.load_data()

    def export(self):
        if not self.shown:
            QMessageBox.warning(self, "خطا", "کاری برای خروجی گرفتن وجود ندارد.")
            return
        rng = self.period.date_range()
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل اکسل", default_filename(rng), "Excel Files (*.xlsx)")
        if not path:
            return
        try:
            export_key_activities_to_excel(
                path, self.shown, rng,
                owner=None if self.admin else self.technician, show_owner=self.admin)
            QMessageBox.information(self, "موفق", f"فایل اکسل ذخیره شد:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "خطا", f"خطا در ایجاد فایل اکسل:\n{exc}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activities_page.py -q`
Expected: `14 passed`

- [ ] **Step 5: Run the whole suite, then commit**

Run: `.venv/Scripts/python.exe -m pytest -q` — Expected: all pass.

```bash
git add ui/key_activities_page.py tests/test_key_activities_page.py
git commit -m "Add key activities page with owner and read-only admin modes"
```

---

### Task 6: Wire into the app, user permission, version and docs

**Files:**
- Modify: `ui/main_window.py` (import + two small blocks)
- Modify: `ui/technicians_page.py` (checkbox + column)
- Modify: `version.txt`, `README.md`
- Test: `tests/test_key_activities_integration.py`

**Interfaces:**
- Consumes: `KeyActivitiesPage(db_session, technician, admin=False)` (Task 5); `Technician.can_log_key_activities` (Task 1); fixtures `qapp`, `db`, `owner`, `other`, `admin`, `dialogs`.
- Produces: `MainWindow.tab_key_activities` (owner tab, only when flagged), `MainWindow.tab_admin_key` (admin tab); `TechniciansPage.chk_key_activities` (`QCheckBox`), users table column 6 `"کارهای شاخص"` showing `"✓"` / `"–"`.

- [ ] **Step 1: Write the failing tests — `tests/test_key_activities_integration.py`**

```python
import pytest

from database.models import Technician
from ui.main_window import MainWindow
from ui.technicians_page import TechniciansPage

OWNER_TAB = "کارهای شاخص IT"
ADMIN_TAB = "گزارش کارهای شاخص"


@pytest.fixture
def open_window(qapp, dialogs):
    windows = []

    def _open(tech):
        win = MainWindow(tech)
        windows.append(win)
        return win

    yield _open
    for win in windows:
        win.db_session.close()


def _titles(win):
    return [win.tabs.tabText(i) for i in range(win.tabs.count())]


def test_flagged_user_gets_entry_tab_after_daily_entry(db, owner, open_window):
    titles = _titles(open_window(owner))
    assert OWNER_TAB in titles and ADMIN_TAB not in titles
    assert titles.index(OWNER_TAB) == 1   # owner فقط بخش IT دارد: تب ثبت روزانه، سپس این تب


def test_admin_gets_report_tab_after_site_reports(db, admin, open_window):
    titles = _titles(open_window(admin))
    assert ADMIN_TAB in titles and OWNER_TAB not in titles
    assert titles.index(ADMIN_TAB) == titles.index("گزارشات کلی واحد سایت") + 1


def test_flagged_admin_gets_both_tabs(db, admin, open_window):
    admin.can_log_key_activities = True
    db.commit()
    titles = _titles(open_window(admin))
    assert OWNER_TAB in titles and ADMIN_TAB in titles


def test_plain_technician_gets_neither(db, other, open_window):
    titles = _titles(open_window(other))
    assert OWNER_TAB not in titles and ADMIN_TAB not in titles


def _row_of(page, tech):
    return next(i for i, t in enumerate(page.techs) if t.id == tech.id)


def test_admin_grants_access_to_existing_user(qapp, db, admin, other, dialogs):
    page = TechniciansPage(db, admin)
    assert page.table.horizontalHeaderItem(6).text() == "کارهای شاخص"
    page.table.selectRow(_row_of(page, other))
    assert not page.chk_key_activities.isChecked()
    page.chk_key_activities.setChecked(True)
    page.save_technician()
    db.refresh(other)
    assert other.can_log_key_activities is True
    assert page.table.item(_row_of(page, other), 6).text() == "✓"
    assert not page.chk_key_activities.isChecked()   # clear_form پس از ذخیره


def test_selecting_flagged_user_checks_box(qapp, db, admin, owner, dialogs):
    page = TechniciansPage(db, admin)
    page.table.selectRow(_row_of(page, owner))
    assert page.chk_key_activities.isChecked()
    assert page.table.item(_row_of(page, admin), 6).text() == "–"


def test_new_user_with_access(qapp, db, admin, dialogs):
    page = TechniciansPage(db, admin)
    page.txt_name.setText("کاربر جدید")
    page.txt_user.setText("newuser")
    page.txt_pass.setText("pw")
    page.chk_key_activities.setChecked(True)
    page.save_technician()
    created = db.query(Technician).filter_by(username="newuser").one()
    assert created.can_log_key_activities is True
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activities_integration.py -q`
Expected: FAIL — tab titles missing / `AttributeError: 'TechniciansPage' object has no attribute 'chk_key_activities'`

- [ ] **Step 3: Wire the tabs in `ui/main_window.py`**

Add the import after `from ui.admin_reports_page import AdminReportsPage`:

```python
from ui.key_activities_page import KeyActivitiesPage
```

After the entry-tabs loop (right after the line `            self.entry_tabs[dept] = page`, before the `# --- «گزارش‌های من»` comment), add:

```python

        # --- کارهای شاخص IT: فقط کاربرانی که تیکِ «ثبت کارهای شاخص» دارند ---
        if self.technician.can_log_key_activities:
            self.tab_key_activities = KeyActivitiesPage(self.db_session, self.technician)
            self.tabs.addTab(self.tab_key_activities, "کارهای شاخص IT")
```

In the admin block, right after the line `            self.tabs.addTab(self.tab_admin_site, "گزارشات کلی واحد سایت")`, add:

```python

            # گزارش کارهای شاخص IT: همه‌ی کاربران، فقط‌خواندنی
            self.tab_admin_key = KeyActivitiesPage(self.db_session, self.technician, admin=True)
            self.tabs.addTab(self.tab_admin_key, "گزارش کارهای شاخص")
```

- [ ] **Step 4: Add the permission checkbox and column in `ui/technicians_page.py`**

1. Import: change `QComboBox, QMessageBox, QAbstractItemView)` in the top import to `QComboBox, QMessageBox, QAbstractItemView, QCheckBox)`.

2. After the `self.cmb_dept.addItem("هر دو بخش", "BOTH")` line, add:

```python

        # اجازه‌ی ثبت در تبِ «کارهای شاخص IT» (مستقل از نقش)
        self.chk_key_activities = QCheckBox("ثبت کارهای شاخص")
        self.chk_key_activities.setToolTip("این کاربر تبِ «کارهای شاخص IT» را می‌بیند و در آن ثبت می‌کند.")
```

3. After `form_layout.addWidget(self.cmb_dept)` add:

```python
        form_layout.addWidget(self.chk_key_activities)
```

4. Replace the table column setup:

```python
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["شناسه", "نام", "داخلی", "نام کاربری", "نقش (Role)", "بخش"])
```

with:

```python
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["شناسه", "نام", "داخلی", "نام کاربری", "نقش (Role)", "بخش", "کارهای شاخص"])
```

5. In `load_technicians`, after `self.table.setItem(row, 5, QTableWidgetItem(dept_label))` add:

```python
            self.table.setItem(row, 6, QTableWidgetItem("✓" if t.can_log_key_activities else "–"))
```

6. In `on_row_selected`, after `self.cmb_dept.setCurrentIndex(idx if idx >= 0 else 0)` add:

```python
        self.chk_key_activities.setChecked(bool(t.can_log_key_activities))
```

7. In `clear_form`, after `self.cmb_dept.setCurrentIndex(0)` add:

```python
        self.chk_key_activities.setChecked(False)
```

8. In `save_technician`, after `ext = self.txt_ext.text().strip()` add:

```python
        key_access = self.chk_key_activities.isChecked()
```

   In the edit branch, after `tech.department = dept` add:

```python
            tech.can_log_key_activities = key_access
```

   In the new-user branch, change the `Technician(...)` call so that after `department=dept,` it also passes:

```python
                can_log_key_activities=key_access,
```

- [ ] **Step 5: Run the integration tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_key_activities_integration.py -q`
Expected: `7 passed`

- [ ] **Step 6: Bump version and document**

Replace the content of `version.txt` with:

```
1.6.0
```

In `README.md`, after the line starting with `- **گزارش‌ها:**`, add:

```markdown
- **کارهای شاخص IT:** کاربرانی که در «مدیریت کاربران» تیکِ «ثبت کارهای شاخص» دارند، تبِ
  «کارهای شاخص IT» را می‌بینند: کارهای آزاد (یک‌روزه یا پروژه‌ی چندهفته‌ای) با دسته، اهمیت،
  وضعیت، درصد پیشرفت و تاریخچه‌ی به‌روزرسانی ثبت می‌شوند و برای هر بازه یک خروجی اکسلِ
  سه‌شیتی (کارها، گزارش پیشرفت، جمع‌بندی) گرفته می‌شود. ادمین در تبِ «گزارش کارهای شاخص»
  کارهای همه را فقط‌خواندنی می‌بیند.
```

In `README.md`, after the `## اجرا` section's closing code fence and the line `ورود پیش‌فرض: ...`, add:

````markdown

## تست‌ها

```
pip install pytest
python -m pytest -q
```

تست‌ها روی یک دیتابیس SQLite موقت اجرا می‌شوند و به دیتابیس واقعی دست نمی‌زنند.
````

- [ ] **Step 7: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (models 5, service 24, exporter 5, period filter 4, dialog 7, page 14, integration 7 = 66).

- [ ] **Step 8: Commit**

```bash
git add ui/main_window.py ui/technicians_page.py version.txt README.md tests/test_key_activities_integration.py
git commit -m "Wire key activities tabs and user permission; bump version to 1.6.0"
```

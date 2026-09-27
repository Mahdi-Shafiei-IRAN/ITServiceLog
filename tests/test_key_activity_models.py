from datetime import date

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

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


def test_key_activities_access_rule(db, owner, other, admin):
    assert admin.can_use_key_activities()       # مدیر بدون تیک
    assert owner.can_use_key_activities()       # کارشناس با تیک
    assert not other.can_use_key_activities()   # کارشناس بدون تیک
    other.can_log_key_activities = None          # ردیف قدیمیِ NULL
    assert not other.can_use_key_activities()


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


def test_migrate_skips_lock_timeout_when_nothing_to_add(tmp_path, monkeypatch):
    """روی دیتابیس به‌روز، حتی وقتی دیالکت postgresql تشخیص داده شود، کاری اجرا نمی‌شود."""
    up_to_date = create_engine(f"sqlite:///{(tmp_path / 'uptodate.sqlite').as_posix()}")
    Base.metadata.create_all(bind=up_to_date)
    monkeypatch.setattr(connection, "engine", up_to_date)
    monkeypatch.setattr(up_to_date.dialect, "name", "postgresql")

    connection._migrate()  # نباید هیچ استثنایی بدهد (چون ستونی برای اضافه شدن نیست)
    up_to_date.dispose()


def _prepare_old_pg_engine(tmp_path, name):
    """موتور SQLite که جای یک PostgreSQل قدیمی را می‌گیرد (بدون ستون تازه)."""
    old = create_engine(f"sqlite:///{(tmp_path / name).as_posix()}")
    with old.begin() as conn:
        conn.execute(text(
            "CREATE TABLE technicians (id INTEGER PRIMARY KEY, full_name VARCHAR(100) NOT NULL, "
            "internal_extension VARCHAR(20), username VARCHAR(50) NOT NULL UNIQUE, "
            "password_hash VARCHAR(128) NOT NULL, role VARCHAR(20), department VARCHAR(10), "
            "is_active BOOLEAN)"))
    Base.metadata.create_all(bind=old)
    return old


class _FakeOrig(Exception):
    """جایگزینِ استثنای خامِ DBAPI با pgcode دلخواه برای شبیه‌سازی خطاهای PostgreSQL."""
    def __init__(self, pgcode):
        super().__init__("fake dbapi error")
        self.pgcode = pgcode


def test_migrate_wraps_postgres_lock_timeout_in_persian_runtime_error(tmp_path, monkeypatch):
    """فقط قفل lock_timeout (SQLSTATE 55P03) باید با پیام فارسی روشن گزارش شود."""
    old = _prepare_old_pg_engine(tmp_path, "old_pg_lock.sqlite")
    monkeypatch.setattr(connection, "engine", old)
    monkeypatch.setattr(old.dialect, "name", "postgresql")

    def fake_begin():
        raise OperationalError("ALTER TABLE ...", {}, _FakeOrig("55P03"))
    monkeypatch.setattr(old, "begin", fake_begin)

    with pytest.raises(RuntimeError) as excinfo:
        connection._migrate()
    assert "همه‌ی نسخه‌های باز برنامه را ببندید" in str(excinfo.value)
    assert excinfo.value.__cause__ is not None

    insp = inspect(old)
    assert "can_log_key_activities" not in {c["name"] for c in insp.get_columns("technicians")}
    old.dispose()


def test_migrate_reraises_non_lock_timeout_postgres_error_unchanged(tmp_path, monkeypatch):
    """خطای دیگرِ PostgreSQL (pgcode متفاوت) نباید به RuntimeError عمومی بدل شود."""
    old = _prepare_old_pg_engine(tmp_path, "old_pg_other.sqlite")
    monkeypatch.setattr(connection, "engine", old)
    monkeypatch.setattr(old.dialect, "name", "postgresql")

    def fake_begin():
        raise OperationalError("ALTER TABLE ...", {}, _FakeOrig("42601"))  # خطای نحوی، نه قفل
    monkeypatch.setattr(old, "begin", fake_begin)

    with pytest.raises(OperationalError):
        connection._migrate()
    old.dispose()


def test_migrate_reraises_postgres_error_without_pgcode_unchanged(tmp_path, monkeypatch):
    """خطایی که اصلاً pgcode ندارد هم باید بدون تغییر propagate شود."""
    old = _prepare_old_pg_engine(tmp_path, "old_pg_no_pgcode.sqlite")
    monkeypatch.setattr(connection, "engine", old)
    monkeypatch.setattr(old.dialect, "name", "postgresql")

    def fake_begin():
        raise OperationalError("ALTER TABLE ...", {}, Exception("boom"))
    monkeypatch.setattr(old, "begin", fake_begin)

    with pytest.raises(OperationalError):
        connection._migrate()
    old.dispose()

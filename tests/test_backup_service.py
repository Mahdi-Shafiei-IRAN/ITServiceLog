import os
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, Technician
from services import backup_service as bk


def _source(tmp_path):
    path = tmp_path / "src.sqlite"
    url = f"sqlite:///{path}"
    eng = create_engine(url)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all([Technician(full_name="الف", username="a", password_hash="x", role="Technician"),
                   Technician(full_name="ب", username="b", password_hash="x", role="Technician"),
                   Technician(full_name=r"O'Brien \ IT", username="c", password_hash="x", role="Technician")])
        s.commit()
    eng.dispose()
    return url


def test_filename_is_jalali():
    assert bk.backup_filename(date(2026, 10, 7)) == "ITServiceLog_1405-07-15.sql"


def test_backup_is_a_postgres_sql_dump(tmp_path):
    url = _source(tmp_path)
    out = tmp_path / "bk"
    path, counts, removed = bk.backup_database(str(out), 3, url, datetime(2026, 10, 7, 13))
    assert os.path.basename(path) == "ITServiceLog_1405-07-15.sql"
    assert counts["technicians"] == 3 and removed == []
    sql = open(path, encoding="utf-8").read()
    assert "SET standard_conforming_strings = on;" in sql
    assert "CREATE TABLE technicians" in sql and "id SERIAL NOT NULL" in sql
    assert "setval(pg_get_serial_sequence('technicians', 'id')" in sql
    # کوتیشن دوبرابر می‌شود ولی بک‌اسلش نه (وگرنه متن هنگام برگرداندن خراب می‌شود)
    assert r"'O''Brien \ IT'" in sql
    assert "'الف'" in sql
    assert sql.endswith("COMMIT;\n")
    assert not any(f.endswith(".partial") for f in os.listdir(out))


def test_keeps_only_last_three_days(tmp_path):
    url = _source(tmp_path)
    out = tmp_path / "bk"
    (out).mkdir()
    (out / "notes.txt").write_text("x")          # فایل‌های دیگر دست نمی‌خورند
    start = datetime(2026, 10, 4, 13)
    for i in range(5):
        _, _, removed = bk.backup_database(str(out), 3, url, start + timedelta(days=i))
    names = sorted(f for f in os.listdir(out) if f.endswith(".sql"))
    assert names == ["ITServiceLog_1405-07-14.sql", "ITServiceLog_1405-07-15.sql",
                     "ITServiceLog_1405-07-16.sql"]
    assert removed == ["ITServiceLog_1405-07-13.sql"]
    assert (out / "notes.txt").exists()


def test_failed_backup_keeps_old_ones(tmp_path):
    url = _source(tmp_path)
    out = tmp_path / "bk"
    for i in range(3):
        bk.backup_database(str(out), 3, url, datetime(2026, 10, 4 + i, 13))
    before = sorted(os.listdir(out))
    bad = f"sqlite:///{tmp_path / 'missing' / 'nope.sqlite'}"
    try:
        bk.backup_database(str(out), 3, bad, datetime(2026, 10, 7, 13))
    except Exception:
        pass
    else:
        raise AssertionError("expected failure")
    assert sorted(os.listdir(out)) == before

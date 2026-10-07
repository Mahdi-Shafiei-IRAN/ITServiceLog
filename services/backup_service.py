r"""بکاپ روزانه‌ی دیتابیس PostgreSQL سرور در یک فایل SQL.

خروجی همان چیزی است که pg_dump به‌صورت متنی می‌دهد: ساخت جدول‌ها و ایندکس‌ها،
همه‌ی ردیف‌ها با همان id ها و تنظیم sequence ها — همه داخل یک تراکنش. برای
برگرداندن، روی یک دیتابیس خالی اجرا می‌شود (psql -f، pgAdmin یا scripts\restore_backup.py).
برای گرفتن بکاپ به pg_dump یا نصب چیز اضافه‌ای روی سیستم نیاز نیست.

هر روز یک فایل با تاریخ شمسی ساخته می‌شود (ITServiceLog_1405-07-15.sql) و فقط
`keep` فایلِ آخر نگه داشته می‌شود. بکاپ اول در فایل موقت نوشته و بررسی می‌شود؛
تا بکاپ جدید سالم کامل نشده باشد، هیچ بکاپ قدیمی‌ای پاک نمی‌شود.

اجرا (همان کاری که Task Scheduler انجام می‌دهد):
    ITServiceLog.exe --backup "D:\Backups\ITServiceLog"
"""
import os
import re
import sys
import time
import traceback
from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from database import config
from database.models import Base
from utils import jalali

DEFAULT_DIR = r"D:\Backups\ITServiceLog"
DEFAULT_KEEP = 3
RETRIES = 3
RETRY_WAIT_SECONDS = 300
INSERT_BATCH = 200
_NAME_RE = re.compile(r"^ITServiceLog_\d{4}-\d{2}-\d{2}\.sql$")
_END = "COMMIT;\n"


def backup_filename(day):
    return f"ITServiceLog_{jalali.fmt(day, '-')}.sql"


def _pg_dialect():
    """دیالکت PostgreSQL برای نوشتن مقادیر به‌صورت متن داخل دستورها.

    فایل با standard_conforming_strings = on شروع می‌شود؛ پس بک‌اسلش نباید دوبرابر شود
    (دیالکتِ بدون اتصال پیش‌فرض دوبرابرش می‌کند و متن‌ها هنگام برگرداندن خراب می‌شوند).
    """
    pg = postgresql.dialect()
    pg._backslash_escapes = False
    return pg


def _sql(stmt, pg):
    return str(stmt.compile(dialect=pg, compile_kwargs={"literal_binds": True})).strip() + ";\n"


def _dump(source_url, dest_path, now):
    """کل دیتابیس را به‌صورت یک فایل SQL قابل اجرا روی PostgreSQL می‌نویسد."""
    pg = _pg_dialect()
    tables = Base.metadata.sorted_tables
    counts = {}
    src = create_engine(source_url, future=True)
    try:
        with src.connect() as s, open(dest_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"-- ITServiceLog backup {jalali.fmt(now)} {now:%H:%M} ({now:%Y-%m-%d})\n"
                    "-- Restore into an EMPTY database:\n"
                    "--   psql -h <server> -U itapp -d <new_db> -f <this file>\n\n"
                    "SET client_encoding = 'UTF8';\n"
                    "SET standard_conforming_strings = on;\n"
                    "BEGIN;\n\n")
            for table in tables:
                f.write(_sql(CreateTable(table), pg))
                for index in sorted(table.indexes, key=lambda i: i.name):
                    f.write(_sql(CreateIndex(index), pg))
                f.write("\n")
            for table in tables:
                query = select(table).order_by(*table.primary_key.columns)
                rows = [dict(r._mapping) for r in s.execute(query)]
                counts[table.name] = len(rows)
                for i in range(0, len(rows), INSERT_BATCH):
                    f.write(_sql(table.insert().values(rows[i:i + INSERT_BATCH]), pg))
                if "id" in table.c:
                    # شماره‌ی بعدیِ id ها از همان جایی ادامه پیدا کند که روی سرور بود
                    f.write(f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                            f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table.name};\n")
            f.write("\n" + _END)
    finally:
        src.dispose()
    # بررسی: فایل تا انتها نوشته شده باشد
    with open(dest_path, "rb") as f:
        f.seek(-len(_END), os.SEEK_END)
        if f.read() != _END.encode():
            raise RuntimeError("backup file is incomplete")
    return counts


def _rotate(target_dir, keep):
    """فقط `keep` بکاپِ آخر می‌ماند (نام فایل تاریخ شمسی است، پس مرتب‌سازی نامی درست است)."""
    files = sorted(f for f in os.listdir(target_dir) if _NAME_RE.match(f))
    removed = files[:-keep] if keep > 0 else []
    for f in removed:
        os.remove(os.path.join(target_dir, f))
    return removed


def backup_database(target_dir=DEFAULT_DIR, keep=DEFAULT_KEEP, source_url=None, now=None):
    """یک بکاپ می‌گیرد و بکاپ‌های قدیمی را پاک می‌کند. خروجی: (مسیر فایل, شمارش, حذف‌شده‌ها)."""
    now = now or datetime.now()
    source_url = source_url or config.database_url()
    os.makedirs(target_dir, exist_ok=True)

    final = os.path.join(target_dir, backup_filename(now))
    partial = final + ".partial"
    if os.path.exists(partial):
        os.remove(partial)
    try:
        counts = _dump(source_url, partial, now)
    except Exception:
        if os.path.exists(partial):
            os.remove(partial)
        raise
    os.replace(partial, final)  # بکاپِ دوباره در همان روز جایگزین قبلی می‌شود
    removed = _rotate(target_dir, keep)
    return final, counts, removed


def _log(target_dir, message):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} ({jalali.fmt(datetime.now())})  {message}"
    print(line)
    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(os.path.join(target_dir, "backup.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run_cli(argv):
    """`--backup [پوشه] [--keep N]` — کد خروج ۰ یعنی موفق (برای Task Scheduler)."""
    args = [a for a in argv if a != "--backup"]
    keep = DEFAULT_KEEP
    if "--keep" in args:
        i = args.index("--keep")
        keep = int(args[i + 1])
        del args[i:i + 2]
    target_dir = args[0] if args else DEFAULT_DIR

    if not config.is_configured():
        _log(target_dir, "FAILED: config.json / db_url not found")
        return 2
    # اگر سرور لحظه‌ای در دسترس نبود، چند بار دیگر هم امتحان می‌کنیم
    for attempt in range(1, RETRIES + 1):
        try:
            path, counts, removed = backup_database(target_dir, keep)
            break
        except Exception as exc:
            _log(target_dir, f"FAILED (attempt {attempt}/{RETRIES}): {exc}\n{traceback.format_exc()}")
            if attempt == RETRIES:
                return 1
            time.sleep(RETRY_WAIT_SECONDS)
    total = sum(counts.values())
    msg = f"OK  {os.path.basename(path)}  ({total} rows)"
    if removed:
        msg += "  removed: " + ", ".join(removed)
    _log(target_dir, msg)
    return 0


if __name__ == "__main__":
    sys.exit(run_cli(sys.argv[1:]))

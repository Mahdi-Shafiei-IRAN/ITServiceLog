r"""بکاپ روزانه‌ی دیتابیس سرور در یک فایل SQLite.

خروجی یک دیتابیس کاملِ برنامه است (همان جدول‌ها و همان id ها)؛ پس:
  • می‌شود مستقیم بازش کرد (DB Browser for SQLite یا خود برنامه با ITSERVICELOG_DB)
  • برای برگرداندن روی سرور کافی است:
        python scripts\migrate_to_postgres.py --source <فایل بکاپ> --force

هر روز یک فایل با تاریخ شمسی ساخته می‌شود (ITServiceLog_1405-07-15.sqlite) و فقط
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

from sqlalchemy import create_engine, func, select, text

from database import config
from database.models import Base
from utils import jalali

DEFAULT_DIR = r"D:\Backups\ITServiceLog"
DEFAULT_KEEP = 3
RETRIES = 3
RETRY_WAIT_SECONDS = 300
_NAME_RE = re.compile(r"^ITServiceLog_\d{4}-\d{2}-\d{2}\.sqlite$")


def backup_filename(day):
    return f"ITServiceLog_{jalali.fmt(day, '-')}.sqlite"


def _copy(source_url, dest_path):
    """همه‌ی جدول‌ها را از دیتابیس منبع در یک فایل SQLite تازه کپی می‌کند."""
    src = create_engine(source_url, future=True)
    dst = create_engine(f"sqlite:///{dest_path}", future=True)
    counts = {}
    try:
        Base.metadata.create_all(dst)
        with src.connect() as s, dst.begin() as d:
            for table in Base.metadata.sorted_tables:
                rows = [dict(r._mapping) for r in s.execute(select(table))]
                if rows:
                    d.execute(table.insert(), rows)
                counts[table.name] = len(rows)
        # بررسی: تعداد ردیف‌های فایل باید با منبع یکی باشد و فایل سالم باشد
        with dst.connect() as d:
            for table in Base.metadata.sorted_tables:
                n = d.execute(select(func.count()).select_from(table)).scalar()
                if n != counts[table.name]:
                    raise RuntimeError(f"row count mismatch in {table.name}: {n} != {counts[table.name]}")
            ok = d.execute(text("PRAGMA integrity_check")).scalar()
            if ok != "ok":
                raise RuntimeError(f"integrity_check: {ok}")
    finally:
        src.dispose()
        dst.dispose()
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
        counts = _copy(source_url, partial)
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

r"""برگرداندن یک فایل بکاپ (ITServiceLog_*.sql) روی یک دیتابیس PostgreSQL خالی.

برای امنیت، روی دیتابیسی که جدول‌های برنامه را دارد اجرا نمی‌شود؛ پس اول یک دیتابیس
تازه بسازید (مثلاً روی سرور:  CREATE DATABASE itservicelog_restore OWNER itapp;)
و بعد:

    python scripts\restore_backup.py "D:\Backups\ITServiceLog\ITServiceLog_1405-07-15.sql" ^
        --target "postgresql+psycopg2://itapp:PASSWORD@10.0.13.12:5432/itservicelog_restore"

همین کار با psql روی خود سرور هم انجام می‌شود:
    psql -h 10.0.13.12 -U itapp -d itservicelog_restore -f ITServiceLog_1405-07-15.sql

بعد از بررسی، یا db_url برنامه را به دیتابیس جدید عوض کنید یا نام دیتابیس‌ها را جابه‌جا کنید.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import create_engine, inspect  # noqa: E402

from database.models import Base  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="بازگردانی بکاپ SQL روی PostgreSQL خالی")
    parser.add_argument("backup", help="مسیر فایل ITServiceLog_*.sql")
    parser.add_argument("--target", required=True, help="آدرس دیتابیس مقصدِ خالی")
    args = parser.parse_args()

    engine = create_engine(args.target, future=True)
    existing = set(inspect(engine).get_table_names()) & set(Base.metadata.tables)
    if existing:
        sys.exit("مقصد خالی نیست (جدول‌های برنامه را دارد): " + ", ".join(sorted(existing)) +
                 "\nیک دیتابیس تازه بسازید و دوباره اجرا کنید.")

    with open(args.backup, encoding="utf-8") as f:
        sql = f.read()
    raw = engine.raw_connection()
    try:
        raw.autocommit = True        # BEGIN/COMMIT داخل خود فایل است
        with raw.cursor() as cur:
            cur.execute(sql)
    finally:
        raw.close()
    print("بازگردانی انجام شد.")


if __name__ == "__main__":
    main()

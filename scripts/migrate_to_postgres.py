r"""مهاجرت داده‌ها از دیتابیس محلی SQLite به PostgreSQL سرور.

این اسکریپت داده‌های موجود (کاربران، سیستم‌ها، کارمندان، خدمات و گزارش‌ها) را با
حفظ شناسه‌ها (id) به دیتابیس PostgreSQL منتقل می‌کند و در پایان مقدار sequence ها
را هماهنگ می‌کند تا رکوردهای بعدی درست شماره بگیرند.

پیش‌نیاز:
    pip install psycopg2-binary
    (روی سیستمی که نسخه‌ی توسعه دارید؛ در نسخه‌ی نصبی برنامه از قبل هست.)

نمونه‌ی اجرا (ویندوز):
    python scripts\migrate_to_postgres.py ^
        --target "postgresql+psycopg2://itapp:PASSWORD@SRV-DB:5432/itservicelog"

    # منبع پیش‌فرض: %APPDATA%\ITServiceLog\database.sqlite
    # برای منبع دلخواه:  --source "C:\path\to\database.sqlite"
    # اگر مقصد از قبل داده دارد و می‌خواهید ادامه دهید: --force

اگر --target ندهید، از db_url داخل config.json خوانده می‌شود (در صورت وجود).
"""
import argparse
import os
import sys

# ریشه‌ی پروژه را به مسیر اضافه می‌کنیم تا ماژول‌های برنامه قابل import باشند
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def default_source():
    appdata = os.getenv("APPDATA")
    if appdata:
        path = os.path.join(appdata, "ITServiceLog", "database.sqlite")
        if os.path.exists(path):
            return path
    return None


def order_tasks_parents_first(rows):
    """ردیف‌های جدول tasks را طوری مرتب می‌کند که هر والد پیش از فرزندش بیاید
    تا کلید خارجی خودارجاع (parent_task_id) هنگام درج نقض نشود."""
    by_id = {r["id"]: r for r in rows}
    ordered, seen = [], set()

    def add(row):
        pid = row.get("parent_task_id")
        if pid and pid in by_id and pid not in seen:
            add(by_id[pid])
        if row["id"] not in seen:
            seen.add(row["id"])
            ordered.append(row)

    for r in rows:
        add(r)
    return ordered


def main():
    parser = argparse.ArgumentParser(description="مهاجرت SQLite → PostgreSQL")
    parser.add_argument("--source", help="مسیر فایل database.sqlite (پیش‌فرض: APPDATA)")
    parser.add_argument("--target", help="آدرس اتصال PostgreSQL (postgresql+psycopg2://...)")
    parser.add_argument("--force", action="store_true",
                        help="حتی اگر مقصد از قبل داده داشته باشد ادامه بده")
    args = parser.parse_args()

    # --- منبع ---
    source = args.source or default_source()
    if not source or not os.path.exists(source):
        sys.exit("خطا: فایل منبع SQLite پیدا نشد. با --source مسیر آن را بدهید.")
    source_url = "sqlite:///" + source.replace("\\", "/")

    # --- مقصد ---
    target_url = args.target
    if not target_url:
        from database import config
        target_url = config.load_config().get("db_url")
    if not target_url:
        sys.exit("خطا: آدرس مقصد داده نشد. با --target بدهید یا در config.json تنظیم کنید.")
    if target_url.startswith("sqlite"):
        sys.exit("خطا: مقصد نباید SQLite باشد؛ یک آدرس PostgreSQL بدهید.")

    print(f"منبع : {source}")
    print(f"مقصد : {target_url.split('@')[-1]}")   # رمز را چاپ نمی‌کنیم

    # ابتدا اسکیمای منبع را با ساختار فعلی هماهنگ می‌کنیم (ستون‌های جدید را اضافه می‌کند)
    os.environ["ITSERVICELOG_DB"] = source_url
    from database.connection import init_db, engine as source_engine
    init_db()

    from sqlalchemy import create_engine, text
    from database.models import Base

    target_engine = create_engine(target_url, future=True)

    # جدول‌ها را روی مقصد می‌سازیم (اگر نباشند)
    Base.metadata.create_all(bind=target_engine)

    is_postgres = target_engine.dialect.name == "postgresql"

    # --- بررسی خالی بودن مقصد ---
    with target_engine.connect() as tconn:
        existing = tconn.execute(text("SELECT COUNT(*) FROM technicians")).scalar() or 0
    if existing and not args.force:
        sys.exit(f"مقصد از قبل {existing} کاربر دارد. برای ادامه --force را اضافه کنید "
                 "(داده‌های تکراری ممکن است ایجاد شود).")

    # --- کپی جدول‌به‌جدول به ترتیب وابستگی‌ها ---
    total = 0
    with source_engine.connect() as sconn, target_engine.begin() as tconn:
        for table in Base.metadata.sorted_tables:
            rows = [dict(r._mapping) for r in sconn.execute(table.select())]
            if not rows:
                print(f"  {table.name}: خالی")
                continue
            if table.name == "tasks":
                rows = order_tasks_parents_first(rows)
            tconn.execute(table.insert(), rows)
            total += len(rows)
            print(f"  {table.name}: {len(rows)} ردیف منتقل شد")

        # --- هماهنگ‌سازی sequence ها (فقط PostgreSQL) ---
        if is_postgres:
            for table in Base.metadata.sorted_tables:
                if "id" in table.c:
                    tconn.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                        f"(SELECT COALESCE(MAX(id), 1) FROM {table.name}))"))
            print("  sequence ها هماهنگ شدند")

    print(f"\nپایان موفق: مجموعاً {total} ردیف منتقل شد.")
    print("حالا برنامه را با همان config.json (آدرس PostgreSQL) اجرا کنید.")


if __name__ == "__main__":
    main()

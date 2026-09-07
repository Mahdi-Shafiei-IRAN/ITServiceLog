"""ساخت فایل seed برای نصب‌کننده.

از دیتابیس فعلی برنامه (در %APPDATA%\\ITServiceLog\\database.sqlite) یک کپی
می‌گیرد و گزارش‌ها را از آن حذف می‌کند تا فقط «کاربران، کارمندان و عملیات»
باقی بماند. نتیجه در assets/seed.sqlite ذخیره می‌شود و build.ps1 آن را داخل
بسته قرار می‌دهد تا هر سیستم تازه با همین داده‌ی پایه بالا بیاید.

خروجی کد:
    0 = seed ساخته شد
    2 = دیتابیس منبع پیدا نشد (build بدون seed ادامه می‌دهد)
"""
import os
import shutil
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, "seed.sqlite")

# جدول‌هایی که نباید در seed باشند (داده‌ی هر سیستم مخصوص خودش است)
STRIP_TABLES = ["service_record_tasks", "service_records"]


def source_db():
    appdata = os.getenv("APPDATA")
    if not appdata:
        return None
    path = os.path.join(appdata, "ITServiceLog", "database.sqlite")
    return path if os.path.exists(path) else None


def main():
    src = source_db()
    if not src:
        print("make_seed: source database not found; building without seed.")
        # اگر seed قدیمی مانده، حذفش کن تا داده‌ی کهنه توزیع نشود
        if os.path.exists(SEED):
            os.remove(SEED)
        return 2

    shutil.copyfile(src, SEED)

    conn = sqlite3.connect(SEED)
    try:
        cur = conn.cursor()
        existing = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        for tbl in STRIP_TABLES:
            if tbl in existing:
                cur.execute(f"DELETE FROM {tbl}")
        conn.commit()
        cur.execute("VACUUM")
        conn.commit()

        techs = cur.execute("SELECT COUNT(*) FROM technicians").fetchone()[0]
        tasks = cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        print(f"make_seed: seed built -> {techs} users, {tasks} operations")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

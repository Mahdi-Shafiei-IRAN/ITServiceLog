r"""انتشار یک نسخه‌ی ساخته‌شده برای همه‌ی کاربران (به‌روزرسانی از داخل برنامه).

فایل نصبی release\ITServiceLog-Setup-<version>.exe در جدول app_releases دیتابیس سرور
قرار می‌گیرد؛ برنامه‌ی کاربران حداکثر تا دو ساعت بعد (یا در اولین اجرا) اعلان
به‌روزرسانی نشان می‌دهد. فایل نصبیِ دو نسخه‌ی آخر در دیتابیس می‌ماند.

ساده‌ترین راه: دابل‌کلیک روی publish.bat
یا:
    python scripts\publish_release.py --notes "تقویم شمسی و بکاپ روزانه"
    python scripts\publish_release.py --version 1.6.6 --installer "D:\...\Setup.exe"

آدرس دیتابیس از --db، یا deploy.json (همان که build استفاده می‌کند)، یا config.json خوانده می‌شود.
"""
import argparse
import getpass
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import create_engine  # noqa: E402

from database import config  # noqa: E402
from services import update_service  # noqa: E402


def _db_url(arg):
    if arg:
        return arg
    deploy = os.path.join(ROOT, "deploy.json")
    if os.path.exists(deploy):
        with open(deploy, encoding="utf-8-sig") as f:
            url = (json.load(f) or {}).get("db_url")
        if url:
            return url
    if config.is_configured():
        return config.database_url()
    sys.exit("آدرس دیتابیس پیدا نشد (--db یا deploy.json).")


def main():
    parser = argparse.ArgumentParser(description="انتشار نسخه‌ی جدید برای کاربران")
    parser.add_argument("--version", help="پیش‌فرض: version.txt")
    parser.add_argument("--installer", help=r"پیش‌فرض: release\ITServiceLog-Setup-<version>.exe")
    parser.add_argument("--notes", default="", help="توضیح تغییرات برای نمایش به کاربران")
    parser.add_argument("--db", help="آدرس دیتابیس سرور")
    args = parser.parse_args()

    if args.version:
        version = args.version
    else:
        with open(os.path.join(ROOT, "version.txt"), encoding="utf-8-sig") as f:
            version = f.read().strip()
    installer = args.installer or os.path.join(ROOT, "release", f"ITServiceLog-Setup-{version}.exe")
    if not os.path.exists(installer):
        sys.exit(f"فایل نصبی پیدا نشد: {installer}\nاول build.bat را اجرا کنید.")

    engine = create_engine(_db_url(args.db), future=True)
    try:
        current = update_service.latest_release(engine)
        if current and update_service.parse_version(current["version"]) > update_service.parse_version(version):
            sys.exit(f"نسخه‌ی جدیدتری ({current['version']}) از قبل منتشر شده است.")
        size = update_service.publish(engine, installer, version, args.notes.strip(),
                                      published_by=getpass.getuser())
    finally:
        engine.dispose()
    print(f"نسخه‌ی {version} منتشر شد ({size / 1024 / 1024:.1f} MB). "
          "کاربران در اجرای بعدی یا حداکثر تا دو ساعت دیگر اعلان به‌روزرسانی می‌بینند.")


if __name__ == "__main__":
    main()

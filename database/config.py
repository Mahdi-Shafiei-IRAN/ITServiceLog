r"""پیکربندی اتصال به دیتابیس و احراز هویت اکتیودایرکتوری.

ترتیب جست‌وجوی فایل پیکربندی (اولین موردی که پیدا شود استفاده می‌شود):
  1. متغیر محیطی ITSERVICELOG_CONFIG (مسیر کامل فایل json)
  2. کنار فایل اجرایی برنامه:  <exe_dir>\config.json
  3. %PROGRAMDATA%\ITServiceLog\config.json
  4. کنار سورس پروژه: <project>\config.json

نمونه‌ی محتوای config.json برای اجرای شبکه‌ای روی سرور شرکت:

{
  "db_url": "mssql+pyodbc://@SRV-APP\\SQLEXPRESS/ITServiceLog?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes",
  "ad": {
    "enabled": true,
    "domain": "company.local",
    "auto_create_users": true
  }
}

اگر فایلی نباشد، برنامه مثل قبل روی SQLite محلی (%APPDATA%) کار می‌کند.
"""
import json
import os
import sys

_CACHE = None


def _exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config_candidates():
    paths = []
    env = os.getenv("ITSERVICELOG_CONFIG")
    if env:
        paths.append(env)
    paths.append(os.path.join(_exe_dir(), "config.json"))
    program_data = os.getenv("PROGRAMDATA")
    if program_data:
        paths.append(os.path.join(program_data, "ITServiceLog", "config.json"))
    paths.append(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"))
    return paths


def load_config(force=False):
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    data = {}
    for path in config_candidates():
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f) or {}
                data["_source"] = path
                break
            except Exception as exc:  # پیکربندی خراب نباید جلوی اجرا را بگیرد
                print(f"config: failed to read {path}: {exc}")
    _CACHE = data
    return data


def local_sqlite_path():
    app_data = os.getenv("APPDATA") or _exe_dir()
    db_dir = os.path.join(app_data, "ITServiceLog")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "database.sqlite")


def database_url():
    """آدرس اتصال دیتابیس؛ متغیر محیطی بر فایل پیکربندی اولویت دارد."""
    url = os.getenv("ITSERVICELOG_DB") or load_config().get("db_url")
    if url:
        return url.strip()
    return f"sqlite:///{local_sqlite_path()}"


def is_sqlite():
    return database_url().startswith("sqlite")


def ad_config():
    ad = load_config().get("ad") or {}
    return {
        "enabled": bool(ad.get("enabled", False)),
        "domain": (ad.get("domain") or "").strip(),
        "auto_create_users": bool(ad.get("auto_create_users", True)),
        "default_role": ad.get("default_role", "Technician"),
        "default_department": ad.get("default_department", "IT"),
    }

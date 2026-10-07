"""به‌روزرسانی خودکار از طریق دیتابیس سرور.

فایل نصبیِ هر نسخه داخل جدول app_releases روی همان PostgreSQL ذخیره می‌شود؛ پس
کلاینت‌ها برای آپدیت به اینترنت، شیر شبکه یا فلش نیاز ندارند و فایل نصبی (که
config.json سرور را دارد) هیچ‌جای عمومی منتشر نمی‌شود.

این جدول عمداً جدا از Base مدل‌هاست تا بکاپ روزانه، seed و مهاجرت فایل‌های حجیم
نصبی را با خودشان نبرند. فقط اسکریپت انتشار (scripts/publish_release.py) جدول را
می‌سازد؛ کلاینت‌ها فقط می‌خوانند.
"""
import hashlib
import os
import sys
from datetime import datetime

from sqlalchemy import (Column, DateTime, Integer, LargeBinary, String, func, inspect,
                        select)
from sqlalchemy.orm import declarative_base, deferred

ReleaseBase = declarative_base()

CHUNK = 2 * 1024 * 1024
KEEP_RELEASES = 2      # فایل نصبیِ چند نسخه‌ی آخر در دیتابیس بماند


class AppRelease(ReleaseBase):
    __tablename__ = "app_releases"
    id = Column(Integer, primary_key=True)
    version = Column(String(20), unique=True, nullable=False)
    notes = Column(String(2000))
    file_name = Column(String(200), nullable=False)
    size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    data = deferred(Column(LargeBinary, nullable=False))
    published_at = Column(DateTime, default=datetime.now)
    published_by = Column(String(100))


def parse_version(text):
    """«1.6.10» → (1, 6, 10) تا مقایسه عددی باشد نه متنی."""
    try:
        return tuple(int(p) for p in str(text).strip().split("."))
    except ValueError:
        return (0,)


def current_version():
    """نسخه‌ی برنامه‌ی در حال اجرا (version.txt داخل بسته یا کنار سورس)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(base, "version.txt"), encoding="utf-8-sig") as f:
            return f.read().strip()
    except OSError:
        return "0"


def latest_release(engine):
    """جدیدترین نسخه‌ی منتشرشده (بدون بارگذاری فایل) یا None."""
    if not inspect(engine).has_table(AppRelease.__tablename__):
        return None
    table = AppRelease.__table__
    cols = [table.c.id, table.c.version, table.c.notes, table.c.file_name,
            table.c.size, table.c.sha256, table.c.published_at]
    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(select(*cols))]
    return max(rows, key=lambda r: parse_version(r["version"])) if rows else None


def newer_release(engine, version=None):
    """اگر نسخه‌ای جدیدتر از نسخه‌ی فعلی منتشر شده باشد، مشخصاتش؛ وگرنه None."""
    rel = latest_release(engine)
    if rel and parse_version(rel["version"]) > parse_version(version or current_version()):
        return rel
    return None


def download(engine, release, dest_path, progress=None):
    """فایل نصبی را تکه‌تکه می‌خواند، در dest_path می‌نویسد و sha256 را بررسی می‌کند."""
    data_col = AppRelease.__table__.c.data
    digest = hashlib.sha256()
    done = 0
    tmp = dest_path + ".part"
    with engine.connect() as conn, open(tmp, "wb") as f:
        while done < release["size"]:
            n = min(CHUNK, release["size"] - done)
            chunk = conn.execute(
                select(func.substr(data_col, done + 1, n))
                .where(AppRelease.__table__.c.id == release["id"])).scalar()
            if not chunk:
                break
            chunk = bytes(chunk)
            f.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, release["size"])
    if done != release["size"] or digest.hexdigest() != release["sha256"]:
        os.remove(tmp)
        raise RuntimeError("فایل دانلودشده ناقص یا خراب است؛ دوباره تلاش کنید.")
    os.replace(tmp, dest_path)
    return dest_path


def publish(engine, installer_path, version, notes="", published_by=None, keep=KEEP_RELEASES):
    """فایل نصبی را در دیتابیس منتشر می‌کند (نسخه‌ی تکراری جایگزین می‌شود)."""
    with open(installer_path, "rb") as f:
        data = f.read()
    ReleaseBase.metadata.create_all(engine)
    table = AppRelease.__table__
    with engine.begin() as conn:
        conn.execute(table.delete().where(table.c.version == version))
        conn.execute(table.insert().values(
            version=version, notes=notes or None, file_name=os.path.basename(installer_path),
            size=len(data), sha256=hashlib.sha256(data).hexdigest(), data=data,
            published_at=datetime.now(), published_by=published_by))
        # فقط چند نسخه‌ی آخر نگه داشته می‌شود تا دیتابیس بزرگ نشود
        rows = conn.execute(select(table.c.id, table.c.version)).all()
        old = sorted(rows, key=lambda r: parse_version(r.version))[:-keep] if keep > 0 else []
        if old:
            conn.execute(table.delete().where(table.c.id.in_([r.id for r in old])))
    return len(data)

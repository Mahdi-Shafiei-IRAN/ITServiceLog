import os
import shutil
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from database import config
from database.models import Base, Technician, Task, DEPT_IT

DB_URL = config.database_url()
db_path = config.local_sqlite_path() if DB_URL.startswith("sqlite") else None

# برای SQL Server / PostgreSQL روی سرور، pool_pre_ping اتصال‌های قطع‌شده را ترمیم می‌کند
_engine_kwargs = {"echo": False, "future": True}
if not DB_URL.startswith("sqlite"):
    _engine_kwargs.update(pool_pre_ping=True, pool_recycle=1800)

engine = create_engine(DB_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _seed_path():
    """مسیر فایل seed همراه برنامه (کاربران + عملیات پیش‌فرض)."""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", "seed.sqlite")


def _install_seed_if_fresh():
    """روی نصب تازه‌ی تک‌کاربره (SQLite بدون دیتابیس)، seed همراه بسته را کپی می‌کند.

    دیتابیس موجود هرگز بازنویسی نمی‌شود؛ پس داده‌ی کاربر از بین نمی‌رود.
    در حالت سرور (SQL Server) اصلاً اجرا نمی‌شود.
    """
    if not db_path or os.path.exists(db_path):
        return
    seed = _seed_path()
    if os.path.exists(seed):
        try:
            shutil.copyfile(seed, db_path)
        except Exception:
            # اگر کپی seed شکست خورد، برنامه با دیتابیس خالی ادامه می‌دهد
            pass


# ستون‌هایی که در نسخه‌های جدید اضافه شده‌اند: (جدول, ستون, تعریف SQL)
_NEW_COLUMNS = [
    ("technicians", "department", "VARCHAR(10)"),
    ("tasks", "department", "VARCHAR(10)"),
    ("tasks", "requires_name", "BOOLEAN"),
    ("tasks", "position", "INTEGER"),
    ("service_records", "department", "VARCHAR(10)"),
    ("service_records", "report_date", "DATE"),
    ("service_record_tasks", "quantity", "INTEGER"),
    ("service_record_tasks", "person_name", "VARCHAR(100)"),
    ("service_record_tasks", "person_extension", "VARCHAR(20)"),
    ("service_record_tasks", "system_name", "VARCHAR(100)"),
    ("service_record_tasks", "note", "VARCHAR(300)"),
]


def _migrate():
    """ستون‌های جدید را به دیتابیس‌های قدیمی اضافه می‌کند (بدون از دست رفتن داده)."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, column, ddl in _NEW_COLUMNS:
            if table not in existing_tables:
                continue
            cols = {c["name"] for c in inspector.get_columns(table)}
            if column in cols:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    # مقداردهی پیش‌فرض رکوردهای قدیمی
    with engine.begin() as conn:
        if "tasks" in existing_tables:
            conn.execute(text(
                "UPDATE tasks SET department = :d WHERE department IS NULL"), {"d": DEPT_IT})
            conn.execute(text(
                "UPDATE tasks SET requires_name = 0 WHERE requires_name IS NULL"))
            # ترتیب اولیه‌ی رکوردهای قدیمی بر اساس شناسه تا جابه‌جایی دستی بعداً ممکن شود
            conn.execute(text(
                "UPDATE tasks SET position = id WHERE position IS NULL OR position = 0"))
        if "technicians" in existing_tables:
            conn.execute(text(
                "UPDATE technicians SET department = :d WHERE department IS NULL"), {"d": DEPT_IT})
        if "service_records" in existing_tables:
            conn.execute(text(
                "UPDATE service_records SET department = :d WHERE department IS NULL"), {"d": DEPT_IT})
            conn.execute(text(
                "UPDATE service_records SET report_date = DATE(created_at) "
                "WHERE report_date IS NULL" if DB_URL.startswith("sqlite") else
                "UPDATE service_records SET report_date = CAST(created_at AS DATE) "
                "WHERE report_date IS NULL"))
        if "service_record_tasks" in existing_tables:
            conn.execute(text(
                "UPDATE service_record_tasks SET quantity = 1 WHERE quantity IS NULL"))


def _propagate_department(db):
    """بخشِ دسته‌های اصلی را روی همه‌ی زیرمجموعه‌هایشان اعمال می‌کند."""
    changed = False
    roots = db.query(Task).filter(Task.parent_task_id.is_(None)).all()

    def walk(task, dept):
        nonlocal changed
        for sub in task.sub_tasks:
            if sub.department != dept:
                sub.department = dept
                changed = True
            walk(sub, dept)

    for root in roots:
        walk(root, root.department or DEPT_IT)
    if changed:
        db.commit()


def init_db():
    _install_seed_if_fresh()
    Base.metadata.create_all(bind=engine)
    _migrate()

    with SessionLocal() as db:
        # ساخت کاربر ادمین پیش‌فرض اگر وجود نداشت
        if not db.query(Technician).first():
            admin = Technician(
                full_name="مدیر سیستم",
                internal_extension="100",
                username="admin",
                password_hash="admin",  # رمز عبور: admin
                role="Administrator",
                department="BOTH",
                is_active=True,
            )
            db.add(admin)
            db.commit()
        _propagate_department(db)

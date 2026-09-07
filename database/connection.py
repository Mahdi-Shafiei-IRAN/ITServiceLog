import os
import sys
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Technician

# مسیر ذخیره دیتابیس در ویندوز
app_data = os.getenv('APPDATA')
db_dir = os.path.join(app_data, 'ITServiceLog')
os.makedirs(db_dir, exist_ok=True)
db_path = os.path.join(db_dir, 'database.sqlite')

engine = create_engine(f'sqlite:///{db_path}', echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _seed_path():
    """مسیر فایل seed همراه برنامه (کاربران + عملیات پیش‌فرض)."""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", "seed.sqlite")


def _install_seed_if_fresh():
    """روی نصب تازه (بدون دیتابیس)، اگر seed همراه بسته باشد آن را کپی می‌کند.

    دیتابیس موجود هرگز بازنویسی نمی‌شود؛ پس داده‌ی کاربر از بین نمی‌رود.
    """
    if os.path.exists(db_path):
        return
    seed = _seed_path()
    if os.path.exists(seed):
        try:
            shutil.copyfile(seed, db_path)
        except Exception:
            # اگر کپی seed شکست خورد، برنامه با دیتابیس خالی ادامه می‌دهد
            pass


def init_db():
    _install_seed_if_fresh()
    Base.metadata.create_all(bind=engine)
    
    # ساخت کاربر ادمین پیش‌فرض اگر وجود نداشت
    with SessionLocal() as db:
        if not db.query(Technician).first():
            # در نسخه واقعی رمز عبور باید هش شود (مثلا با bcrypt) 
            # اما اینجا برای سادگی تست، هش ساده قرار دادیم
            admin = Technician(
                full_name="مدیر سیستم",
                internal_extension="100",
                username="admin",
                password_hash="admin", # رمز عبور: admin
                role="Administrator",
                is_active=True
            )
            db.add(admin)
            db.commit()
import os
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

def init_db():
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
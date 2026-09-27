from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# بخش‌های سازمان: واحد IT و واحد سایت
DEPT_IT = "IT"
DEPT_SITE = "SITE"
DEPARTMENTS = [(DEPT_IT, "واحد IT"), (DEPT_SITE, "واحد سایت")]
DEPT_LABELS = dict(DEPARTMENTS)

# ---------------------------------------------------------------------------
# مقادیر ثابتِ واحد سایت (دقیقاً مطابق فهرست‌های کشویی فایل «گزارش مدیریت»)
# این‌ها منبعِ یکتای گزینه‌های کشویی در دو تبِ واحد سایت هستند.
# ---------------------------------------------------------------------------
SITE_PLATFORMS = ["سایت", "اینستاگرام", "ایتا", "بله", "تلگرام", "واتساپ", "آپارات", "سایر"]
SITE_ACTIVITY_TYPES = ["تولید محتوا", "انتشار محتوا", "پایش", "پاسخگویی",
                       "طراحی گرافیک", "بروزرسانی سایت", "تبلیغات", "گزارش گیری"]
SITE_STATUSES = ["در حال انجام", "انجام شد", "در انتظار تأیید", "منتظر اطلاعات", "لغو شد"]
SITE_PAGE_STATUSES = ["فعال", "نیمه‌فعال", "غیرفعال"]


class Technician(Base):
    __tablename__ = 'technicians'
    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    internal_extension = Column(String(20))
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), default='Technician') # 'Technician' or 'Administrator'
    # بخش کاری کاربر: IT ، SITE یا BOTH (دسترسی به هر دو صفحه)
    department = Column(String(10), default=DEPT_IT)
    is_active = Column(Boolean, default=True)
    # اجازه‌ی ثبت در تبِ «کارهای شاخص IT» (مستقل از نقش ادمین)
    can_log_key_activities = Column(Boolean, default=False)

    def departments(self):
        """لیست بخش‌هایی که این کاربر اجازه‌ی ثبت در آن‌ها را دارد."""
        if self.role == "Administrator" or (self.department or "") == "BOTH":
            return [DEPT_IT, DEPT_SITE]
        return [self.department or DEPT_IT]

    def can_use_key_activities(self):
        """اجازه‌ی ثبت در تبِ «کارهای شاخص IT».

        مدیرها همیشه دسترسی دارند (بدون نیاز به تیک)؛ بقیه فقط با تیکِ
        «ثبت کارهای شاخص» در «مدیریت کاربران IT».
        """
        return self.role == "Administrator" or bool(self.can_log_key_activities)


class SystemDevice(Base):
    __tablename__ = 'systems'
    id = Column(Integer, primary_key=True)
    system_name = Column(String(100), nullable=False)
    asset_number = Column(String(50))
    ip_address = Column(String(50))
    is_active = Column(Boolean, default=True)


class Employee(Base):
    __tablename__ = 'employees'
    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    internal_extension = Column(String(20))
    system_id = Column(Integer, ForeignKey('systems.id'), nullable=True)
    is_active = Column(Boolean, default=True)

    system = relationship("SystemDevice")


class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    parent_task_id = Column(Integer, ForeignKey('tasks.id'), nullable=True)
    title = Column(String(100), nullable=False)
    # بخش مربوطه؛ فقط روی دسته‌های اصلی معنا دارد و زیرمجموعه‌ها از پدر ارث می‌برند
    department = Column(String(10), default=DEPT_IT)
    # خدماتی مثل «ارتقا»، «اسمبل» و «نصب ویندوز» تک‌تک و با نام فرد ثبت می‌شوند
    requires_name = Column(Boolean, default=False)
    # ترتیب نمایش (اولویت) بین هم‌ردیف‌ها؛ عدد کوچک‌تر بالاتر
    position = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # اصلاح رابطه برای ساختار درختی (پدر-فرزندی)
    sub_tasks = relationship("Task", back_populates="parent")
    parent = relationship("Task", back_populates="sub_tasks", remote_side=[id])


class ServiceRecord(Base):
    """یک «برگه‌ی روزانه» برای هر کارشناس، در هر تاریخ و هر بخش."""
    __tablename__ = 'service_records'
    id = Column(Integer, primary_key=True)

    # Relationships
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False)
    requester_employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    system_id = Column(Integer, ForeignKey('systems.id'), nullable=True)

    # Historical Snapshots (Crucial for data integrity)
    technician_name_snapshot = Column(String(100))
    requester_name_snapshot = Column(String(100))
    requester_extension_snapshot = Column(String(20))
    system_name_snapshot = Column(String(100))

    department = Column(String(10), default=DEPT_IT)
    report_date = Column(Date, default=date.today)

    short_description = Column(String(300))
    created_at = Column(DateTime, default=datetime.now)

    tasks = relationship("ServiceRecordTask", back_populates="record")
    technician = relationship("Technician")
    requester = relationship("Employee")

    def total_count(self):
        return sum((t.quantity or 1) for t in self.tasks)


class ServiceRecordTask(Base):
    """یک خط از برگه‌ی روزانه: یا «تعداد» یک خدمت کلی، یا یک مورد نام‌دار."""
    __tablename__ = 'service_record_tasks'
    id = Column(Integer, primary_key=True)
    service_record_id = Column(Integer, ForeignKey('service_records.id'))
    task_id = Column(Integer, ForeignKey('tasks.id'))

    quantity = Column(Integer, default=1)
    # فقط برای خدمات نام‌دار (ارتقا / اسمبل / نصب ویندوز) پر می‌شود
    person_name = Column(String(100))
    person_extension = Column(String(20))
    system_name = Column(String(100))
    note = Column(String(300))

    record = relationship("ServiceRecord", back_populates="tasks")
    task = relationship("Task")


# ===========================================================================
# واحد سایت — دو جدولِ مستقل مطابق دو شیتِ فایل «گزارش مدیریت»
# (شیت ۱: گزارش روزانه، شیت ۲: پایش شبکه‌ها)
# هر ردیف مستقیماً یک سطر از اکسل است؛ به تاریخ و کارشناسِ ثبت‌کننده گره خورده.
# ===========================================================================
class SiteDailyActivity(Base):
    """یک ردیف از «گزارش روزانه»ی واحد سایت (شیت اولِ فایل مدیریت)."""
    __tablename__ = 'site_daily_activities'
    id = Column(Integer, primary_key=True)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False)
    technician_name_snapshot = Column(String(100))
    report_date = Column(Date, default=date.today, index=True)

    platform = Column(String(50))        # نام بستر (کشویی)
    activity_type = Column(String(50))   # نوع فعالیت (کشویی)
    description = Column(String(500))     # شرح کار انجام‌شده
    status = Column(String(50))           # وضعیت (کشویی)
    note = Column(String(500))            # توضیحات
    created_at = Column(DateTime, default=datetime.now)

    technician = relationship("Technician")


class SiteNetworkStat(Base):
    """یک ردیف از «پایش شبکه‌ها»ی واحد سایت (شیت دومِ فایل مدیریت)."""
    __tablename__ = 'site_network_stats'
    id = Column(Integer, primary_key=True)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False)
    technician_name_snapshot = Column(String(100))
    report_date = Column(Date, default=date.today, index=True)

    platform = Column(String(50))         # نام بستر (کشویی)
    followers = Column(Integer)           # تعداد دنبال‌کننده/عضو
    impressions = Column(Integer)         # بازدید/Impression
    engagement = Column(Integer)          # تعامل/Engagement
    posts = Column(Integer)               # تعداد پست
    stories = Column(Integer)             # تعداد استوری
    growth = Column(String(50))           # رشد نسبت به قبل (متن آزاد: مثلاً +۵٪)
    page_status = Column(String(50))      # وضعیت صفحه (کشویی)
    note = Column(String(500))            # توضیحات
    created_at = Column(DateTime, default=datetime.now)

    technician = relationship("Technician")


# ===========================================================================
# کارهای شاخص IT — کارهای آزاد (بدون فهرست خدمات از پیش تعریف‌شده)
# هر کار یک‌روزه یا پروژه‌ی چندهفته‌ای است و تاریخچه‌ی به‌روزرسانی دارد.
# ===========================================================================
KEY_STATUS_PLANNED = "برنامه‌ریزی"
KEY_STATUS_IN_PROGRESS = "در حال انجام"
KEY_STATUS_DONE = "انجام شد"
KEY_STATUS_ON_HOLD = "متوقف"
KEY_STATUS_CANCELLED = "لغو شد"
KEY_STATUSES = [KEY_STATUS_PLANNED, KEY_STATUS_IN_PROGRESS, KEY_STATUS_DONE,
                KEY_STATUS_ON_HOLD, KEY_STATUS_CANCELLED]

KEY_PRIORITY_NORMAL = "عادی"
KEY_PRIORITY_HIGH = "مهم"
KEY_PRIORITY_TOP = "خیلی مهم"
KEY_PRIORITIES = [KEY_PRIORITY_NORMAL, KEY_PRIORITY_HIGH, KEY_PRIORITY_TOP]

# فقط پیشنهاد است؛ کاربر هر دسته‌ی دیگری را هم می‌تواند تایپ کند
KEY_CATEGORIES_DEFAULT = ["شبکه", "سرور", "امنیت", "نرم‌افزار", "سخت‌افزار",
                          "خرید و تأمین", "آموزش", "سایر"]


class KeyActivity(Base):
    """یک «کار شاخص» که صاحبش آزادانه ثبت و در طول زمان به‌روز می‌کند."""
    __tablename__ = 'key_activities'
    id = Column(Integer, primary_key=True)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False, index=True)
    technician_name_snapshot = Column(String(100))

    title = Column(String(200), nullable=False)
    category = Column(String(50))                    # متن آزاد با پیشنهاد
    priority = Column(String(20), default=KEY_PRIORITY_NORMAL)
    status = Column(String(30), default=KEY_STATUS_IN_PROGRESS)
    progress = Column(Integer, default=0)            # ۰ تا ۱۰۰
    start_date = Column(Date, nullable=False, default=date.today, index=True)
    end_date = Column(Date, nullable=True)           # با «انجام شد» خودکار پر می‌شود
    description = Column(String(1000))               # شرح کار
    result = Column(String(1000))                    # نتیجه / دستاورد
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    technician = relationship("Technician")
    updates = relationship("KeyActivityUpdate", back_populates="activity",
                           cascade="all, delete-orphan")


class KeyActivityUpdate(Base):
    """یک به‌روزرسانی در خط زمانیِ یک کار شاخص (پیشرفت و وضعیت پس از آن)."""
    __tablename__ = 'key_activity_updates'
    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey('key_activities.id'), nullable=False, index=True)
    update_date = Column(Date, nullable=False, default=date.today, index=True)
    text = Column(String(1000), nullable=False)
    progress = Column(Integer)                       # درصد پیشرفت پس از این به‌روزرسانی
    status = Column(String(30))                      # وضعیت پس از این به‌روزرسانی
    author_name_snapshot = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)

    activity = relationship("KeyActivity", back_populates="updates")

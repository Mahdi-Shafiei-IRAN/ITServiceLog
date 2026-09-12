from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# بخش‌های سازمان: واحد IT و واحد سایت
DEPT_IT = "IT"
DEPT_SITE = "SITE"
DEPARTMENTS = [(DEPT_IT, "واحد IT"), (DEPT_SITE, "واحد سایت")]
DEPT_LABELS = dict(DEPARTMENTS)


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

    def departments(self):
        """لیست بخش‌هایی که این کاربر اجازه‌ی ثبت در آن‌ها را دارد."""
        if self.role == "Administrator" or (self.department or "") == "BOTH":
            return [DEPT_IT, DEPT_SITE]
        return [self.department or DEPT_IT]


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

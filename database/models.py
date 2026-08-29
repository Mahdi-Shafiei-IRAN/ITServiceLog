from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Technician(Base):
    __tablename__ = 'technicians'
    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    internal_extension = Column(String(20))
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), default='Technician') # 'Technician' or 'Administrator'
    is_active = Column(Boolean, default=True)

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
    is_active = Column(Boolean, default=True)
    
    # اصلاح رابطه برای ساختار درختی (پدر-فرزندی)
    sub_tasks = relationship("Task", back_populates="parent")
    parent = relationship("Task", back_populates="sub_tasks", remote_side=[id])

class ServiceRecord(Base):
    __tablename__ = 'service_records'
    id = Column(Integer, primary_key=True)
    
    # Relationships
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False)
    requester_employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    system_id = Column(Integer, ForeignKey('systems.id'), nullable=True)
    
    # Historical Snapshots (Crucial for data integrity)
    technician_name_snapshot = Column(String(100))
    requester_name_snapshot = Column(String(100))
    requester_extension_snapshot = Column(String(20))
    system_name_snapshot = Column(String(100))
    
    short_description = Column(String(300))
    created_at = Column(DateTime, default=datetime.now)

    tasks = relationship("ServiceRecordTask", back_populates="record")
    technician = relationship("Technician")
    requester = relationship("Employee")

class ServiceRecordTask(Base):
    __tablename__ = 'service_record_tasks'
    id = Column(Integer, primary_key=True)
    service_record_id = Column(Integer, ForeignKey('service_records.id'))
    task_id = Column(Integer, ForeignKey('tasks.id'))
    
    record = relationship("ServiceRecord", back_populates="tasks")
    task = relationship("Task")
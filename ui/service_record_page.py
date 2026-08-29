from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, 
                               QTextEdit, QMessageBox, QGroupBox, QCompleter)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from database.models import Employee, Task, ServiceRecord, ServiceRecordTask

class ServiceRecordPage(QWidget):
    def __init__(self, db_session: Session, current_technician):
        super().__init__()
        self.db = db_session
        self.technician = current_technician
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # بخش مراجعه‌کننده (فقط فیلدهای متنی آزاد)
        req_group = QGroupBox("مراجعه‌کننده (نام فرد را تایپ کنید)")
        req_layout = QHBoxLayout()
        
        self.txt_req_name = QLineEdit()
        self.txt_req_name.setPlaceholderText("نام شخص (مثلاً: احمد محمدی)...")
        
        self.txt_req_ext = QLineEdit()
        self.txt_req_ext.setPlaceholderText("شماره داخلی...")
        
        self.txt_system = QLineEdit()
        self.txt_system.setPlaceholderText("نام سیستم / IP...")

        req_layout.addWidget(QLabel("نام:"))
        req_layout.addWidget(self.txt_req_name, stretch=2)
        req_layout.addWidget(QLabel("داخلی:"))
        req_layout.addWidget(self.txt_req_ext, stretch=1)
        req_layout.addWidget(QLabel("سیستم:"))
        req_layout.addWidget(self.txt_system, stretch=1)
        req_group.setLayout(req_layout)
        layout.addWidget(req_group)

        # درخت کارها
        task_group = QGroupBox("عملیات انجام‌شده")
        task_layout = QVBoxLayout()
        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderHidden(True)
        task_layout.addWidget(self.task_tree)
        task_group.setLayout(task_layout)
        layout.addWidget(task_group, stretch=1)

        # توضیحات و ثبت
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("توضیح کوتاه (اختیاری)...")
        self.txt_notes.setMaximumHeight(80)
        layout.addWidget(self.txt_notes)

        btn_submit = QPushButton("ثبت گزارش")
        btn_submit.setStyleSheet("background-color: #27AE60; color: white; padding: 10px; font-weight: bold;")
        btn_submit.clicked.connect(self.save_record)
        layout.addWidget(btn_submit)

    def load_data(self):
        """این تابع درخت کارها و لیست تکمیل خودکار نام‌ها را رفرش می‌کند"""
        # پر کردن درخت کارها
        self.task_tree.clear()
        top_tasks = self.db.query(Task).filter_by(parent_task_id=None, is_active=True).all()
        for task in top_tasks:
            parent_item = QTreeWidgetItem(self.task_tree, [task.title])
            parent_item.setData(0, Qt.UserRole, task.id)
            parent_item.setFlags(parent_item.flags() | Qt.ItemIsUserCheckable)
            parent_item.setCheckState(0, Qt.Unchecked)
            self._add_sub_tasks(parent_item, task)
        self.task_tree.expandAll()

        # پیشنهاد خودکار نام‌ها (Auto-complete)
        employees = self.db.query(Employee).filter_by(is_active=True).all()
        names = [emp.full_name for emp in employees]
        completer = QCompleter(names)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.txt_req_name.setCompleter(completer)

    def _add_sub_tasks(self, parent_item, parent_task):
        for sub_task in parent_task.sub_tasks:
            if not sub_task.is_active: continue
            child = QTreeWidgetItem(parent_item, [sub_task.title])
            child.setData(0, Qt.UserRole, sub_task.id)
            child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
            child.setCheckState(0, Qt.Unchecked)
            self._add_sub_tasks(child, sub_task)

    def get_checked_tasks(self, root=None, checked=None):
        if checked is None: checked = []
        iterator = range(self.task_tree.topLevelItemCount()) if root is None else range(root.childCount())
        for i in iterator:
            item = self.task_tree.topLevelItem(i) if root is None else root.child(i)
            if item.checkState(0) == Qt.Checked:
                checked.append(item.data(0, Qt.UserRole))
            self.get_checked_tasks(item, checked)
        return checked

    def save_record(self):
        name = self.txt_req_name.text().strip()
        tasks = self.get_checked_tasks()
        
        if not name or not tasks:
            QMessageBox.warning(self, "خطا", "تایپ کردن نام شخص و انتخاب حداقل یک عملیات الزامی است.")
            return
            
        employee = self.db.query(Employee).filter_by(full_name=name).first()
        if not employee:
            employee = Employee(full_name=name, internal_extension=self.txt_req_ext.text().strip())
            self.db.add(employee)
            self.db.flush() 
        
        record = ServiceRecord(
            technician_id=self.technician.id,
            requester_employee_id=employee.id,
            technician_name_snapshot=self.technician.full_name,
            requester_name_snapshot=employee.full_name,
            requester_extension_snapshot=self.txt_req_ext.text().strip(),
            system_name_snapshot=self.txt_system.text().strip(),
            short_description=self.txt_notes.toPlainText()
        )
        self.db.add(record)
        
        # کلید حل مشکل ثبت نشدن تیک‌ها این دستور است!
        self.db.flush() 
        
        for task_id in tasks:
            self.db.add(ServiceRecordTask(service_record_id=record.id, task_id=task_id))
            
        self.db.commit()
        QMessageBox.information(self, "موفق", "گزارش شما سریعاً ثبت شد.")
        
        self.txt_req_name.clear(); self.txt_req_ext.clear()
        self.txt_system.clear(); self.txt_notes.clear()
        self.load_data()
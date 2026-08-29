from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)
from sqlalchemy.orm import Session
from database.models import Employee

class EmployeesPage(QWidget):
    def __init__(self, db_session: Session):
        super().__init__()
        self.db = db_session
        self.setup_ui()
        self.load_employees()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # فرم ثبت
        form_layout = QHBoxLayout()
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("نام و نام خانوادگی کارمند...")
        self.txt_ext = QLineEdit()
        self.txt_ext.setPlaceholderText("شماره داخلی...")
        
        btn_add = QPushButton("ثبت کارمند جدید")
        btn_add.clicked.connect(self.add_employee)
        
        form_layout.addWidget(self.txt_name)
        form_layout.addWidget(self.txt_ext)
        form_layout.addWidget(btn_add)
        layout.addLayout(form_layout)

        # جدول کارمندان
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["شناسه", "نام کارمند", "داخلی"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def load_employees(self):
        self.table.setRowCount(0)
        employees = self.db.query(Employee).filter_by(is_active=True).all()
        self.table.setRowCount(len(employees))
        
        for row, emp in enumerate(employees):
            self.table.setItem(row, 0, QTableWidgetItem(str(emp.id)))
            self.table.setItem(row, 1, QTableWidgetItem(emp.full_name))
            self.table.setItem(row, 2, QTableWidgetItem(emp.internal_extension or "-"))

    def add_employee(self):
        name = self.txt_name.text().strip()
        ext = self.txt_ext.text().strip()
        
        if not name:
            return QMessageBox.warning(self, "خطا", "نام کارمند الزامی است.")
            
        new_emp = Employee(full_name=name, internal_extension=ext)
        self.db.add(new_emp)
        self.db.commit()
        
        self.txt_name.clear()
        self.txt_ext.clear()
        self.load_employees()
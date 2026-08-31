from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from database.models import Technician

class TechniciansPage(QWidget):
    def __init__(self, db_session: Session):
        super().__init__()
        self.db = db_session
        self.setup_ui()
        self.load_technicians()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("مدیریت کاربران IT")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # فرم ثبت نام کارشناس IT
        form_layout = QHBoxLayout()
        form_layout.setSpacing(8)
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("نام و نام خانوادگی کارشناس...")
        
        self.txt_ext = QLineEdit()
        self.txt_ext.setPlaceholderText("داخلی...")
        
        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("نام کاربری (برای لاگین)...")
        
        self.txt_pass = QLineEdit()
        self.txt_pass.setPlaceholderText("رمز عبور...")
        
        self.cmb_role = QComboBox()
        self.cmb_role.addItems(["Technician", "Administrator"])
        
        btn_add = QPushButton("ثبت / ویرایش کارشناس")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self.add_technician)
        
        form_layout.addWidget(self.txt_name)
        form_layout.addWidget(self.txt_ext)
        form_layout.addWidget(self.txt_user)
        form_layout.addWidget(self.txt_pass)
        form_layout.addWidget(self.cmb_role)
        form_layout.addWidget(btn_add)
        layout.addLayout(form_layout)

        # جدول نمایش کارشناسان
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["شناسه", "نام", "داخلی", "نام کاربری", "نقش (Role)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def load_technicians(self):
        self.table.setRowCount(0)
        techs = self.db.query(Technician).filter_by(is_active=True).all()
        self.table.setRowCount(len(techs))
        
        for row, t in enumerate(techs):
            self.table.setItem(row, 0, QTableWidgetItem(str(t.id)))
            self.table.setItem(row, 1, QTableWidgetItem(t.full_name))
            self.table.setItem(row, 2, QTableWidgetItem(t.internal_extension or "-"))
            self.table.setItem(row, 3, QTableWidgetItem(t.username))
            self.table.setItem(row, 4, QTableWidgetItem("مدیر" if t.role == "Administrator" else "کارشناس"))

    def add_technician(self):
        name = self.txt_name.text().strip()
        user = self.txt_user.text().strip()
        pwd = self.txt_pass.text().strip()
        role = self.cmb_role.currentText()
        
        if not name or not user or not pwd:
            return QMessageBox.warning(self, "خطا", "نام، نام کاربری و رمز عبور الزامی است.")
            
        # بررسی اینکه نام کاربری تکراری نباشد
        existing = self.db.query(Technician).filter_by(username=user).first()
        if existing:
            return QMessageBox.warning(self, "خطا", "این نام کاربری از قبل وجود دارد.")

        new_tech = Technician(
            full_name=name, 
            internal_extension=self.txt_ext.text().strip(),
            username=user,
            password_hash=pwd, # در سیستم‌های بزرگ‌تر این هش می‌شود
            role=role
        )
        self.db.add(new_tech)
        self.db.commit()
        
        self.txt_name.clear(); self.txt_ext.clear(); self.txt_user.clear(); self.txt_pass.clear()
        self.load_technicians()
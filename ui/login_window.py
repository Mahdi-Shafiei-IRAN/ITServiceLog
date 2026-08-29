from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QMessageBox)
from PySide6.QtCore import Qt
from database.connection import SessionLocal
from database.models import Technician

class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ورود به سیستم IT Service Log")
        self.setFixedSize(350, 250)
        self.authenticated_user = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("ورود به سیستم")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("نام کاربری (admin)")
        layout.addWidget(self.txt_username)

        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("رمز عبور (admin)")
        self.txt_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.txt_password)

        btn_login = QPushButton("ورود")
        btn_login.setStyleSheet("background-color: #2563EB; color: white; padding: 10px; font-weight: bold;")
        btn_login.clicked.connect(self.check_login)
        layout.addWidget(btn_login)

    def check_login(self):
        username = self.txt_username.text()
        password = self.txt_password.text()

        with SessionLocal() as db:
            user = db.query(Technician).filter_by(username=username).first()
            # در نسخه نهایی باید از bcrypt.checkpw استفاده شود
            if user and user.password_hash == password:
                self.authenticated_user = user
                self.accept()
            else:
                QMessageBox.warning(self, "خطا", "نام کاربری یا رمز عبور اشتباه است.")
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QMessageBox)
from PySide6.QtCore import Qt
from database.connection import SessionLocal
from database.models import Technician
from ui.theme import make_theme_toggle

class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ورود به سیستم IT Service Log")
        self.setFixedSize(400, 340)
        self.authenticated_user = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(34, 26, 34, 30)

        # نوار بالا: دکمه تغییر تم
        top_bar = QHBoxLayout()
        top_bar.addWidget(make_theme_toggle())
        top_bar.addStretch()
        layout.addLayout(top_bar)

        title = QLabel("IT Service Log")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("برای ورود، نام کاربری و رمز عبور خود را وارد کنید")
        subtitle.setObjectName("Muted")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(6)

        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("نام کاربری")
        self.txt_username.setMinimumHeight(38)
        layout.addWidget(self.txt_username)

        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("رمز عبور")
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setMinimumHeight(38)
        self.txt_password.returnPressed.connect(self.check_login)
        layout.addWidget(self.txt_password)

        layout.addSpacing(6)

        btn_login = QPushButton("ورود به سیستم")
        btn_login.setMinimumHeight(42)
        btn_login.setCursor(Qt.PointingHandCursor)
        btn_login.clicked.connect(self.check_login)
        layout.addWidget(btn_login)

        layout.addStretch()

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
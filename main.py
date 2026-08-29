import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from database.connection import init_db
from ui.login_window import LoginWindow
from ui.main_window import MainWindow

def main():
    # ساخت دیتابیس و کاربر ادمین پیش‌فرض
    init_db()

    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyleSheet("* { font-family: 'Tahoma', 'Segoe UI'; font-size: 13px; }")

    login = LoginWindow()
    if login.exec() == LoginWindow.Accepted:
        window = MainWindow(login.authenticated_user)
        window.showMaximized()
        sys.exit(app.exec())

if __name__ == "__main__":
    main()
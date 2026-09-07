import os
import sys
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from database.connection import init_db
from ui.login_window import LoginWindow
from ui.main_window import MainWindow
from ui.theme import theme


def resource_path(rel):
    """مسیر فایل‌های همراه برنامه، هم در حالت توسعه و هم در بسته‌ی PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def main():
    init_db()
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    icon_path = resource_path(os.path.join("assets", "app.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    theme.apply()  # اعمال تم مدرن (روشن/تیره) روی کل برنامه

    # یک حلقه ایجاد می‌کنیم تا کاربر بتواند خروج (Logout) کند
    while True:
        login = LoginWindow()
        if login.exec() == QDialog.Accepted:
            window = MainWindow(login.authenticated_user)
            window.showMaximized()
            app.exec() # برنامه اینجا منتظر می‌ماند تا پنجره بسته شود
            
            # بررسی اینکه کاربر دکمه خروج را زده یا کل برنامه را بسته است
            if hasattr(window, 'wants_logout') and window.wants_logout:
                continue # برگرد به صفحه لاگین
            else:
                break # خروج کامل از برنامه
        else:
            break

if __name__ == "__main__":
    main()
import os
import sys
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from database.connection import init_db
from database import config
from ui.login_window import LoginWindow
from ui.main_window import MainWindow
from ui.theme import theme


def resource_path(rel):
    """مسیر فایل‌های همراه برنامه، هم در حالت توسعه و هم در بسته‌ی PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def main():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    icon_path = resource_path(os.path.join("assets", "app.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    theme.apply()  # اعمال تم مدرن (روشن/تیره) روی کل برنامه

    # نسخه‌ی نصب‌شده فقط با دیتابیس سرور کار می‌کند؛ اگر config.json نباشد
    # نباید بی‌سروصدا سراغ دیتابیس محلی برود.
    if getattr(sys, "frozen", False) and not config.is_configured():
        QMessageBox.critical(
            None, "پیکربندی سرور یافت نشد",
            "فایل config.json کنار برنامه پیدا نشد یا آدرس دیتابیس (db_url) در آن نیست.\n\n"
            "این برنامه فقط با دیتابیس سرور کار می‌کند. لطفاً با مدیر سیستم تماس بگیرید.")
        return

    # اتصال و ساخت جدول‌ها؛ اگر سرور در دسترس نبود پیام روشن بده (نه کرش)
    try:
        init_db()
    except Exception as exc:
        QMessageBox.critical(
            None, "اتصال به سرور برقرار نشد",
            "اتصال به دیتابیس سرور ممکن نشد. ممکن است سرور خاموش باشد یا آدرس (IP) آن\n"
            "عوض شده باشد. آدرس db_url را در فایل config.json بررسی کنید.\n\n"
            "جزئیات فنی:\n" + str(exc)[:400])
        return

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
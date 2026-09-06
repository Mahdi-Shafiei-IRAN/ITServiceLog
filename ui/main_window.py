from PySide6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
                               QWidget, QPushButton)
from PySide6.QtCore import Qt
from database.connection import SessionLocal
from ui.service_record_page import ServiceRecordPage
from ui.my_reports_page import MyReportsPage
from ui.dashboard_page import DashboardPage
from ui.tasks_page import TasksPage
from ui.technicians_page import TechniciansPage
from ui.admin_reports_page import AdminReportsPage
from ui.theme import set_variant, make_theme_toggle

class MainWindow(QMainWindow):
    def __init__(self, current_technician):
        super().__init__()
        self.technician = current_technician
        self.db_session = SessionLocal()
        self.wants_logout = False # فلگ برای خروج از حساب
        
        self.setWindowTitle(f"IT Service Log - کاربر: {self.technician.full_name} ({self.technician.role})")
        self.setMinimumSize(1100, 768)
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # ----- گوشه تب‌ها: تغییر تم + خروج از حساب -----
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(6, 4, 6, 4)
        corner_layout.setSpacing(8)

        self.btn_theme = make_theme_toggle()
        corner_layout.addWidget(self.btn_theme)

        btn_logout = QPushButton("خروج از حساب")
        set_variant(btn_logout, "danger")
        btn_logout.setCursor(Qt.PointingHandCursor)
        btn_logout.clicked.connect(self.logout)
        corner_layout.addWidget(btn_logout)

        self.tabs.setCornerWidget(corner, Qt.TopLeftCorner)  # گوشه چپ (چون راست‌چین است)
        
        # --- تب‌های مشترک ---
        self.tab_new_record = ServiceRecordPage(self.db_session, self.technician)
        self.tabs.addTab(self.tab_new_record, "ثبت مراجعه جدید")
        
        self.tab_my_reports = MyReportsPage(self.db_session, self.technician)
        self.tabs.addTab(self.tab_my_reports, "گزارش‌های من")

        # --- تب‌های مدیر ---
        if self.technician.role == "Administrator":
            self.tab_admin_reports = AdminReportsPage(self.db_session)
            self.tabs.addTab(self.tab_admin_reports, "جستجو و گزارشات (Excel)")
            self.tab_dashboard = DashboardPage(self.db_session)
            self.tabs.addTab(self.tab_dashboard, "داشبورد مدیریت")
            self.tab_tasks = TasksPage(self.db_session)
            self.tabs.addTab(self.tab_tasks, "مدیریت خدمات")
            self.tab_technicians = TechniciansPage(self.db_session, self.technician)
            self.tabs.addTab(self.tab_technicians, "مدیریت کاربران IT")

        layout.addWidget(self.tabs)

    def logout(self):
        self.wants_logout = True
        self.close() # پنجره را می‌بندد تا فایل main.py لاگین را دوباره باز کند

    def closeEvent(self, event):
        # نخِ ناظرِ جلسهٔ ریموت را قبل از بسته‌شدن (خروج یا Logout) ایمن متوقف کن
        try:
            if hasattr(self, 'tab_new_record') and hasattr(self.tab_new_record, 'stop_watcher'):
                self.tab_new_record.stop_watcher()
        except Exception:
            pass
        super().closeEvent(event)

    def on_tab_changed(self, index):
        current_widget = self.tabs.widget(index)
        if hasattr(current_widget, 'load_data'): current_widget.load_data()
        elif hasattr(current_widget, 'load_tasks'): current_widget.load_tasks()
        elif hasattr(current_widget, 'load_technicians'): current_widget.load_technicians()
        elif hasattr(current_widget, 'load_records'): current_widget.load_records()
        elif hasattr(current_widget, 'refresh_dashboard'): current_widget.refresh_dashboard()
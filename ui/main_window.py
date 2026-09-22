from PySide6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
                               QWidget, QPushButton)
from PySide6.QtCore import Qt
from database.connection import SessionLocal
from ui.daily_entry_page import DailyEntryPage
from ui.site_page import SitePage
from ui.site_reports_page import SiteReportsPage
from ui.my_reports_page import MyReportsPage
# DashboardPage به‌صورت تنبل (فقط هنگام باز شدن تبِ داشبورد) import می‌شود تا
# کتابخانه‌ی سنگین matplotlib در زمان اجرای برنامه بارگذاری نشود و باز شدن سریع‌تر باشد.
from ui.tasks_page import TasksPage
from ui.technicians_page import TechniciansPage
from ui.admin_reports_page import AdminReportsPage
from ui.theme import set_variant, make_theme_toggle
from database.models import DEPT_LABELS, DEPT_SITE, DEPT_IT

class MainWindow(QMainWindow):
    def __init__(self, current_technician):
        super().__init__()
        self.technician = current_technician
        self.db_session = SessionLocal()
        self.wants_logout = False # فلگ برای خروج از حساب
        self._dash_index = None   # ایندکس تب داشبورد (برای ساخت تنبل)
        self.tab_dashboard = None
        
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
        
        # --- یک تب ثبت برای هر بخشی که کاربر به آن دسترسی دارد ---
        # واحد IT: برگه‌ی تیکی/تعدادی. واحد سایت: دو تبِ جدولی مطابق فایل مدیریت.
        self.entry_tabs = {}
        for dept in self.technician.departments():
            if dept == DEPT_SITE:
                page = SitePage(self.db_session, self.technician)
                self.tabs.addTab(page, "واحد سایت")
            else:
                page = DailyEntryPage(self.db_session, self.technician, dept)
                self.tabs.addTab(page, f"ثبت روزانه — {DEPT_LABELS.get(dept, dept)}")
            self.entry_tabs[dept] = page
        
        # --- گزارش‌های شخصی: IT و سایت جدا از هم تا کارِ بخش‌ها قاطی نشود ---
        depts = self.technician.departments()
        has_it = DEPT_IT in depts
        has_site = DEPT_SITE in depts

        if has_it:
            self.tab_my_reports = MyReportsPage(self.db_session, self.technician)
            self.tabs.addTab(self.tab_my_reports,
                             "گزارش‌های من (IT)" if has_site else "گزارش‌های من")
        if has_site:
            self.tab_my_site = SiteReportsPage(self.db_session, technician=self.technician,
                                               admin=False)
            self.tabs.addTab(self.tab_my_site, "گزارش‌های من (سایت)")

        # --- تب‌های مدیر ---
        if self.technician.role == "Administrator":
            self.tab_admin_reports = AdminReportsPage(self.db_session)
            self.tabs.addTab(self.tab_admin_reports, "گزارشات واحد IT (Excel)")
            self.tab_admin_site = SiteReportsPage(self.db_session, technician=None, admin=True)
            self.tabs.addTab(self.tab_admin_site, "گزارشات واحد سایت (Excel)")
            # داشبورد تنبل: یک جای‌گیرنده می‌گذاریم و نمودارها را فقط هنگام اولین باز شدن می‌سازیم
            self.tab_dashboard = None
            self._dash_index = self.tabs.addTab(QWidget(), "داشبورد مدیریت")
            self.tab_tasks = TasksPage(self.db_session)
            self.tabs.addTab(self.tab_tasks, "مدیریت خدمات")
            self.tab_technicians = TechniciansPage(self.db_session, self.technician)
            self.tabs.addTab(self.tab_technicians, "مدیریت کاربران IT")

        layout.addWidget(self.tabs)

    def logout(self):
        self.wants_logout = True
        self.close() # پنجره را می‌بندد تا فایل main.py لاگین را دوباره باز کند

    def on_tab_changed(self, index):
        # ساخت تنبل داشبورد در اولین باز شدن (تا matplotlib در استارتاپ لود نشود)
        if index == self._dash_index and self.tab_dashboard is None:
            from ui.dashboard_page import DashboardPage
            self.tab_dashboard = DashboardPage(self.db_session)
            self.tabs.removeTab(self._dash_index)
            self.tabs.insertTab(self._dash_index, self.tab_dashboard, "داشبورد مدیریت")
            self.tabs.setCurrentIndex(self._dash_index)
            return

        current_widget = self.tabs.widget(index)
        if hasattr(current_widget, 'load_data'): current_widget.load_data()
        elif hasattr(current_widget, 'load_tasks'): current_widget.load_tasks()
        elif hasattr(current_widget, 'load_technicians'): current_widget.load_technicians()
        elif hasattr(current_widget, 'load_records'): current_widget.load_records()
        elif hasattr(current_widget, 'refresh_dashboard'): current_widget.refresh_dashboard()
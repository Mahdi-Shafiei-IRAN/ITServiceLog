from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget, QPushButton
from PySide6.QtCore import Qt
from database.connection import SessionLocal
from ui.service_record_page import ServiceRecordPage
from ui.my_reports_page import MyReportsPage
from ui.dashboard_page import DashboardPage
from ui.tasks_page import TasksPage
from ui.technicians_page import TechniciansPage
from ui.admin_reports_page import AdminReportsPage

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
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border-top: 2px solid #CBD5E1; }
            QTabBar::tab { padding: 10px 20px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #F8FAFC; border-bottom: 2px solid #2563EB; color: #2563EB; }
        """)

        # ----- دکمه خروج (گوشه تب‌ها) -----
        btn_logout = QPushButton("خروج از حساب")
        btn_logout.setStyleSheet("background-color: #EF4444; color: white; padding: 4px 15px; border-radius: 4px; font-weight: bold; margin: 4px;")
        btn_logout.clicked.connect(self.logout)
        self.tabs.setCornerWidget(btn_logout, Qt.TopLeftCorner) # گوشه چپ قرار می‌گیرد (چون راست‌چین است)
        
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
            self.tab_technicians = TechniciansPage(self.db_session)
            self.tabs.addTab(self.tab_technicians, "مدیریت کاربران IT")

        layout.addWidget(self.tabs)

    def logout(self):
        self.wants_logout = True
        self.close() # پنجره را می‌بندد تا فایل main.py لاگین را دوباره باز کند

    def on_tab_changed(self, index):
        current_widget = self.tabs.widget(index)
        if hasattr(current_widget, 'load_data'): current_widget.load_data()
        elif hasattr(current_widget, 'load_tasks'): current_widget.load_tasks()
        elif hasattr(current_widget, 'load_technicians'): current_widget.load_technicians()
        elif hasattr(current_widget, 'load_records'): current_widget.load_records()
        elif hasattr(current_widget, 'refresh_dashboard'): current_widget.refresh_dashboard()
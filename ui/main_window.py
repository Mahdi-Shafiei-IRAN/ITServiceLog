from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget
from database.connection import SessionLocal
from ui.service_record_page import ServiceRecordPage
from ui.my_reports_page import MyReportsPage
from ui.dashboard_page import DashboardPage
from ui.tasks_page import TasksPage
from ui.employees_page import EmployeesPage
from ui.technicians_page import TechniciansPage

class MainWindow(QMainWindow):
    def __init__(self, current_technician):
        super().__init__()
        self.technician = current_technician
        self.db_session = SessionLocal()
        
        self.setWindowTitle(f"IT Service Log - کاربر: {self.technician.full_name} ({self.technician.role})")
        self.setMinimumSize(1024, 768)
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        # اتصال رویداد تغییر تب به تابع رفرش اطلاعات
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border-top: 2px solid #CBD5E1; }
            QTabBar::tab { padding: 10px 20px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #F8FAFC; border-bottom: 2px solid #2563EB; color: #2563EB; }
        """)
        
        # --- تب‌های مشترک (برای همه) ---
        self.tab_new_record = ServiceRecordPage(self.db_session, self.technician)
        self.tabs.addTab(self.tab_new_record, "ثبت مراجعه جدید")
        
        self.tab_my_reports = MyReportsPage(self.db_session, self.technician)
        self.tabs.addTab(self.tab_my_reports, "گزارش‌های من")

        # --- تب‌های اختصاصی فقط برای مدیر (Administrator) ---
        if self.technician.role == "Administrator":
            self.tab_dashboard = DashboardPage(self.db_session)
            self.tabs.addTab(self.tab_dashboard, "داشبورد مدیریت")
            
            self.tab_tasks = TasksPage(self.db_session)
            self.tabs.addTab(self.tab_tasks, "مدیریت خدمات (چک‌باکس‌ها)")
            
            self.tab_technicians = TechniciansPage(self.db_session)
            self.tabs.addTab(self.tab_technicians, "مدیریت کارشناسان IT (یوزرها)")
            
            self.tab_employees = EmployeesPage(self.db_session)
            self.tabs.addTab(self.tab_employees, "لیست کل مراجعین")

        layout.addWidget(self.tabs)

    def on_tab_changed(self, index):
        """هر بار تب عوض می‌شود، صفحه جدید را به صورت خودکار رفرش می‌کند"""
        current_widget = self.tabs.widget(index)
        
        # اگر تب دارای تابع لود دیتا بود، آن را صدا می‌زنیم
        if hasattr(current_widget, 'load_data'):
            current_widget.load_data()
        elif hasattr(current_widget, 'load_tasks'):
            current_widget.load_tasks()
        elif hasattr(current_widget, 'load_technicians'):
            current_widget.load_technicians()
        elif hasattr(current_widget, 'load_records'):
            current_widget.load_records()
        elif hasattr(current_widget, 'refresh_dashboard'):
            current_widget.refresh_dashboard()
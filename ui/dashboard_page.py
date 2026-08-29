from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from sqlalchemy import func

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from database.models import ServiceRecord, ServiceRecordTask, Task, Technician


class StatCard(QFrame):
    """Modern rounded statistic KPI card."""
    def __init__(self, title: str, value: str, subtext: str, bg_color: str = "#2B579A"):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 10px;
                padding: 12px;
            }}
            QLabel {{
                color: white;
                background: transparent;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 13px; font-weight: normal; opacity: 0.9;")
        
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet("font-size: 26px; font-weight: bold;")
        
        lbl_sub = QLabel(subtext)
        lbl_sub.setStyleSheet("font-size: 11px; opacity: 0.8;")
        
        layout.addWidget(lbl_title)
        layout.addWidget(self.lbl_value)
        layout.addWidget(lbl_sub)


class DashboardPage(QWidget):
    def __init__(self, db_session: Session):
        super().__init__()
        self.db = db_session
        self.setup_ui()
        self.refresh_dashboard()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        header = QLabel("داشبورد مدیریت و آمار مراجعات IT")
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #1E293B;")
        main_layout.addWidget(header)

        # KPI Metric Cards Grid
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(15)

        self.card_today = StatCard("مراجعات امروز", "0", "ثبت‌شده امروز", "#0284C7")
        self.card_week = StatCard("مراجعات این هفته", "0", "۷ روز گذشته", "#0D9488")
        self.card_month = StatCard("مراجعات این ماه", "0", "۳۰ روز گذشته", "#6366F1")
        self.card_techs = StatCard("کارشناسان فعال", "0", "آماده ارائه خدمت", "#D97706")

        kpi_layout.addWidget(self.card_today)
        kpi_layout.addWidget(self.card_week)
        kpi_layout.addWidget(self.card_month)
        kpi_layout.addWidget(self.card_techs)
        main_layout.addLayout(kpi_layout)

        # Charts Area
        charts_grid = QGridLayout()
        charts_grid.setSpacing(15)

        # Chart 1: Services by Technician
        self.fig_tech = Figure(figsize=(5, 3.2), facecolor="#F8FAFC")
        self.canvas_tech = FigureCanvas(self.fig_tech)
        self.canvas_tech.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        frame_tech = self._create_chart_container("عملکرد کارشناسان IT", self.canvas_tech)
        charts_grid.addWidget(frame_tech, 0, 0)

        # Chart 2: Most Common Tasks
        self.fig_tasks = Figure(figsize=(5, 3.2), facecolor="#F8FAFC")
        self.canvas_tasks = FigureCanvas(self.fig_tasks)
        self.canvas_tasks.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        frame_tasks = self._create_chart_container("بیشترین درخواست‌ها و خدمات انجام‌شده", self.canvas_tasks)
        charts_grid.addWidget(frame_tasks, 0, 1)

        main_layout.addLayout(charts_grid, stretch=1)

    def _create_chart_container(self, title: str, canvas: QWidget) -> QFrame:
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(container)
        lbl = QLabel(title)
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #334155; margin-bottom: 5px;")
        layout.addWidget(lbl)
        layout.addWidget(canvas)
        return container

    def refresh_dashboard(self):
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        # Fetch Counts
        count_today = self.db.query(ServiceRecord).filter(ServiceRecord.created_at >= today_start).count()
        count_week = self.db.query(ServiceRecord).filter(ServiceRecord.created_at >= week_start).count()
        count_month = self.db.query(ServiceRecord).filter(ServiceRecord.created_at >= month_start).count()
        count_techs = self.db.query(Technician).filter_by(is_active=True).count()

        self.card_today.lbl_value.setText(str(count_today))
        self.card_week.lbl_value.setText(str(count_week))
        self.card_month.lbl_value.setText(str(count_month))
        self.card_techs.lbl_value.setText(str(count_techs))

        # Chart 1: Records grouped by Technician
        tech_data = (
            self.db.query(
                ServiceRecord.technician_name_snapshot, 
                func.count(ServiceRecord.id)
            )
            .group_by(ServiceRecord.technician_name_snapshot)
            .order_by(func.count(ServiceRecord.id).desc())
            .limit(6)
            .all()
        )

        self.fig_tech.clear()
        ax1 = self.fig_tech.add_subplot(111)
        if tech_data:
            names = [d[0] or "نامشخص" for d in tech_data]
            counts = [d[1] for d in tech_data]
            bars = ax1.barh(names, counts, color="#0284C7", height=0.55)
            ax1.bar_label(bars, padding=4, fontsize=9)
            ax1.invert_yaxis()
        ax1.set_facecolor("#F8FAFC")
        ax1.spines[['top', 'right', 'left', 'bottom']].set_visible(False)
        ax1.tick_params(left=False, bottom=False, labelsize=9)
        self.fig_tech.tight_layout()
        self.canvas_tech.draw()

        # Chart 2: Most Common Tasks
        task_data = (
            self.db.query(
                Task.title,
                func.count(ServiceRecordTask.id)
            )
            .join(ServiceRecordTask, Task.id == ServiceRecordTask.task_id)
            .group_by(Task.title)
            .order_by(func.count(ServiceRecordTask.id).desc())
            .limit(5)
            .all()
        )

        self.fig_tasks.clear()
        ax2 = self.fig_tasks.add_subplot(111)
        if task_data:
            titles = [t[0] for t in task_data]
            counts = [t[1] for t in task_data]
            colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]
            ax2.pie(
                counts, 
                labels=titles, 
                autopct='%1.0f%%', 
                startangle=140, 
                colors=colors[:len(counts)],
                textprops={'fontsize': 9}
            )
        self.fig_tasks.tight_layout()
        self.canvas_tasks.draw()
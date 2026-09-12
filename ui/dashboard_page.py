from datetime import datetime, timedelta, date
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
from ui.theme import theme


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
        # با تغییر تم، نمودارها دوباره با رنگ‌های جدید رسم شوند
        theme.changed.connect(self.refresh_dashboard)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        header = QLabel("داشبورد مدیریت و آمار خدمات")
        header.setObjectName("PageTitle")
        main_layout.addWidget(header)

        # KPI Metric Cards Grid
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(15)

        self.card_today = StatCard("خدمات امروز", "0", "مجموع تعداد خدمات امروز", "#0284C7")
        self.card_week = StatCard("خدمات ۷ روز اخیر", "0", "۷ روز گذشته", "#0D9488")
        self.card_month = StatCard("خدمات ۳۰ روز اخیر", "0", "۳۰ روز گذشته", "#6366F1")
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
        self.fig_tech = Figure(figsize=(5, 3.2))
        self.canvas_tech = FigureCanvas(self.fig_tech)
        self.canvas_tech.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        frame_tech = self._create_chart_container("عملکرد کارشناسان IT", self.canvas_tech)
        charts_grid.addWidget(frame_tech, 0, 0)

        # Chart 2: Most Common Tasks
        self.fig_tasks = Figure(figsize=(5, 3.2))
        self.canvas_tasks = FigureCanvas(self.fig_tasks)
        self.canvas_tasks.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        frame_tasks = self._create_chart_container("بیشترین درخواست‌ها و خدمات انجام‌شده", self.canvas_tasks)
        charts_grid.addWidget(frame_tasks, 0, 1)

        main_layout.addLayout(charts_grid, stretch=1)

    def _create_chart_container(self, title: str, canvas: QWidget) -> QFrame:
        container = QFrame()
        container.setObjectName("Card")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 12, 14, 12)
        lbl = QLabel(title)
        lbl.setObjectName("SectionTitle")
        layout.addWidget(lbl)
        layout.addWidget(canvas)
        return container

    def refresh_dashboard(self):
        today = date.today()
        week_start = today - timedelta(days=6)
        month_start = today - timedelta(days=29)

        # مجموع «تعداد» خدمات (نه تعداد برگه‌ها) در هر بازه
        def service_count(since):
            value = (
                self.db.query(func.sum(ServiceRecordTask.quantity))
                .join(ServiceRecord, ServiceRecord.id == ServiceRecordTask.service_record_id)
                .filter(ServiceRecord.report_date >= since)
                .scalar()
            )
            return int(value or 0)

        self.card_today.lbl_value.setText(str(service_count(today)))
        self.card_week.lbl_value.setText(str(service_count(week_start)))
        self.card_month.lbl_value.setText(str(service_count(month_start)))
        self.card_techs.lbl_value.setText(
            str(self.db.query(Technician).filter_by(is_active=True).count()))

        # Chart 1: Records grouped by Technician
        tech_data = (
            self.db.query(
                ServiceRecord.technician_name_snapshot,
                func.sum(ServiceRecordTask.quantity)
            )
            .join(ServiceRecordTask, ServiceRecord.id == ServiceRecordTask.service_record_id)
            .group_by(ServiceRecord.technician_name_snapshot)
            .order_by(func.sum(ServiceRecordTask.quantity).desc())
            .limit(6)
            .all()
        )

        p = theme.palette
        surface = p["surface"]
        text_color = p["text"]

        self.fig_tech.clear()
        self.fig_tech.set_facecolor(surface)
        ax1 = self.fig_tech.add_subplot(111)
        if tech_data:
            names = [d[0] or "نامشخص" for d in tech_data]
            counts = [int(d[1] or 0) for d in tech_data]
            bars = ax1.barh(names, counts, color=p["primary"], height=0.55)
            ax1.bar_label(bars, padding=4, fontsize=9, color=text_color)
            ax1.invert_yaxis()
        ax1.set_facecolor(surface)
        ax1.spines[['top', 'right', 'left', 'bottom']].set_visible(False)
        ax1.tick_params(left=False, bottom=False, labelsize=9, colors=text_color)
        self.fig_tech.tight_layout()
        self.canvas_tech.draw()

        # Chart 2: Most Common Tasks
        task_data = (
            self.db.query(
                Task.title,
                func.sum(ServiceRecordTask.quantity)
            )
            .join(ServiceRecordTask, Task.id == ServiceRecordTask.task_id)
            .group_by(Task.title)
            .order_by(func.sum(ServiceRecordTask.quantity).desc())
            .limit(5)
            .all()
        )

        self.fig_tasks.clear()
        self.fig_tasks.set_facecolor(surface)
        ax2 = self.fig_tasks.add_subplot(111)
        ax2.set_facecolor(surface)
        if task_data:
            titles = [t[0] for t in task_data]
            counts = [int(t[1] or 0) for t in task_data]
            colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]
            ax2.pie(
                counts,
                labels=titles,
                autopct='%1.0f%%',
                startangle=140,
                colors=colors[:len(counts)],
                textprops={'fontsize': 9, 'color': text_color}
            )
        self.fig_tasks.tight_layout()
        self.canvas_tasks.draw()
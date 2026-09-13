from datetime import datetime, timedelta, date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QSizePolicy, QComboBox, QDateEdit
)
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session
from sqlalchemy import func

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from database.models import ServiceRecord, ServiceRecordTask, Task, Technician
from ui.theme import theme


def week_start(d):
    return d - timedelta(days=(d.weekday() - 5) % 7)


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
        theme.changed.connect(self.refresh_dashboard)

    # --------------------------------------------------------------- UI
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header = QLabel("داشبورد مدیریت و آمار خدمات")
        header.setObjectName("PageTitle")
        main_layout.addWidget(header)

        # ---- نوار انتخاب بازه‌ی زمانی نمودارها ----
        filter_bar = QHBoxLayout()
        self.cmb_period = QComboBox()
        for label, key in [
            ("۳۰ روز اخیر", "last30"),
            ("۷ روز اخیر", "last7"),
            ("این هفته", "this_week"),
            ("این ماه", "this_month"),
            ("ماه گذشته", "last_month"),
            ("۹۰ روز اخیر", "last90"),
            ("همه‌ی زمان‌ها", "all"),
            ("بازه‌ی دلخواه", "custom"),
        ]:
            self.cmb_period.addItem(label, key)
        self.cmb_period.currentIndexChanged.connect(self._period_changed)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy/MM/dd")
        self.date_from.setDate(QDate.currentDate().addDays(-29))
        self.date_from.setEnabled(False)
        self.date_from.dateChanged.connect(self.refresh_dashboard)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy/MM/dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setEnabled(False)
        self.date_to.dateChanged.connect(self.refresh_dashboard)

        filter_bar.addWidget(QLabel("بازه‌ی نمودارها:"))
        filter_bar.addWidget(self.cmb_period)
        filter_bar.addWidget(QLabel("از:"))
        filter_bar.addWidget(self.date_from)
        filter_bar.addWidget(QLabel("تا:"))
        filter_bar.addWidget(self.date_to)
        filter_bar.addStretch()
        main_layout.addLayout(filter_bar)

        # ---- کارت‌های KPI ----
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

        # ---- نمودارها ----
        charts_grid = QGridLayout()
        charts_grid.setSpacing(15)

        self.fig_tech = Figure(figsize=(5, 3.0))
        self.canvas_tech = FigureCanvas(self.fig_tech)
        self.canvas_tech.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        charts_grid.addWidget(
            self._create_chart_container("عملکرد کارشناسان (در بازه‌ی انتخابی)", self.canvas_tech), 0, 0)

        self.fig_tasks = Figure(figsize=(5, 3.0))
        self.canvas_tasks = FigureCanvas(self.fig_tasks)
        self.canvas_tasks.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        charts_grid.addWidget(
            self._create_chart_container("بیشترین خدمات انجام‌شده (در بازه)", self.canvas_tasks), 0, 1)

        self.fig_trend = Figure(figsize=(10, 2.8))
        self.canvas_trend = FigureCanvas(self.fig_trend)
        self.canvas_trend.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        charts_grid.addWidget(
            self._create_chart_container("روند روزانه‌ی خدمات", self.canvas_trend), 1, 0, 1, 2)

        charts_grid.setRowStretch(0, 1)
        charts_grid.setRowStretch(1, 1)
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

    # ------------------------------------------------------- بازه‌ی زمانی
    def _period_changed(self):
        is_custom = self.cmb_period.currentData() == "custom"
        self.date_from.setEnabled(is_custom)
        self.date_to.setEnabled(is_custom)
        self.refresh_dashboard()

    def _chart_range(self):
        """(start, end) بازه‌ی نمودارها را برمی‌گرداند (همیشه محدود، نه None)."""
        key = self.cmb_period.currentData()
        today = date.today()
        if key == "last7":
            start, end = today - timedelta(days=6), today
        elif key == "this_week":
            start, end = week_start(today), today
        elif key == "this_month":
            start, end = today.replace(day=1), today
        elif key == "last_month":
            first_this = today.replace(day=1)
            last_prev = first_this - timedelta(days=1)
            start, end = last_prev.replace(day=1), last_prev
        elif key == "last90":
            start, end = today - timedelta(days=89), today
        elif key == "custom":
            start = self.date_from.date().toPython()
            end = self.date_to.date().toPython()
        elif key == "all":
            first = self.db.query(func.min(ServiceRecord.report_date)).scalar()
            start = first or (today - timedelta(days=29))
            end = today
        else:  # last30
            start, end = today - timedelta(days=29), today
        if end < start:
            start, end = end, start
        # سقف امنیتی برای نمودار روزانه (حداکثر ۱۸۰ روز)
        if (end - start).days > 180:
            start = end - timedelta(days=180)
        return start, end

    # --------------------------------------------------------- بازآوری
    def refresh_dashboard(self):
        today = date.today()

        def service_count(start, end=None):
            q = (self.db.query(func.sum(ServiceRecordTask.quantity))
                 .join(ServiceRecord, ServiceRecord.id == ServiceRecordTask.service_record_id)
                 .filter(ServiceRecord.report_date >= start))
            if end is not None:
                q = q.filter(ServiceRecord.report_date <= end)
            return int(q.scalar() or 0)

        self.card_today.lbl_value.setText(str(service_count(today)))
        self.card_week.lbl_value.setText(str(service_count(today - timedelta(days=6))))
        self.card_month.lbl_value.setText(str(service_count(today - timedelta(days=29))))
        self.card_techs.lbl_value.setText(
            str(self.db.query(Technician).filter_by(is_active=True).count()))

        start, end = self._chart_range()
        p = theme.palette
        surface = p["surface"]
        text_color = p["text"]

        def in_range(q):
            return (q.filter(ServiceRecord.report_date >= start)
                     .filter(ServiceRecord.report_date <= end))

        # ---- نمودار ۱: عملکرد کارشناسان (بر اساس شناسه، با نام فعلی) ----
        tech_data = in_range(
            self.db.query(Technician.full_name, func.sum(ServiceRecordTask.quantity))
            .join(ServiceRecord, ServiceRecord.technician_id == Technician.id)
            .join(ServiceRecordTask, ServiceRecord.id == ServiceRecordTask.service_record_id)
        ).group_by(Technician.id, Technician.full_name) \
         .order_by(func.sum(ServiceRecordTask.quantity).desc()).limit(8).all()

        self.fig_tech.clear()
        self.fig_tech.set_facecolor(surface)
        ax1 = self.fig_tech.add_subplot(111)
        if tech_data:
            names = [d[0] or "نامشخص" for d in tech_data]
            counts = [int(d[1] or 0) for d in tech_data]
            bars = ax1.barh(names, counts, color=p["primary"], height=0.6)
            ax1.bar_label(bars, padding=4, fontsize=9, color=text_color)
            ax1.invert_yaxis()
        else:
            ax1.text(0.5, 0.5, "داده‌ای در این بازه نیست", ha="center", va="center",
                     color=text_color, transform=ax1.transAxes)
        ax1.set_facecolor(surface)
        ax1.spines[['top', 'right', 'left', 'bottom']].set_visible(False)
        ax1.tick_params(left=False, bottom=False, labelsize=9, colors=text_color)
        self.fig_tech.tight_layout()
        self.canvas_tech.draw()

        # ---- نمودار ۲: بیشترین خدمات ----
        task_data = in_range(
            self.db.query(Task.title, func.sum(ServiceRecordTask.quantity))
            .join(ServiceRecordTask, Task.id == ServiceRecordTask.task_id)
            .join(ServiceRecord, ServiceRecord.id == ServiceRecordTask.service_record_id)
        ).group_by(Task.title) \
         .order_by(func.sum(ServiceRecordTask.quantity).desc()).limit(6).all()

        self.fig_tasks.clear()
        self.fig_tasks.set_facecolor(surface)
        ax2 = self.fig_tasks.add_subplot(111)
        ax2.set_facecolor(surface)
        if task_data:
            titles = [t[0] for t in task_data]
            counts = [int(t[1] or 0) for t in task_data]
            colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]
            ax2.pie(counts, labels=titles, autopct='%1.0f%%', startangle=140,
                    colors=colors[:len(counts)],
                    textprops={'fontsize': 9, 'color': text_color})
        else:
            ax2.text(0.5, 0.5, "داده‌ای در این بازه نیست", ha="center", va="center",
                     color=text_color, transform=ax2.transAxes)
        self.fig_tasks.tight_layout()
        self.canvas_tasks.draw()

        # ---- نمودار ۳: روند روزانه ----
        trend_rows = in_range(
            self.db.query(ServiceRecord.report_date, func.sum(ServiceRecordTask.quantity))
            .join(ServiceRecordTask, ServiceRecord.id == ServiceRecordTask.service_record_id)
        ).group_by(ServiceRecord.report_date).all()
        by_day = {r[0]: int(r[1] or 0) for r in trend_rows if r[0] is not None}

        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        values = [by_day.get(d, 0) for d in days]

        self.fig_trend.clear()
        self.fig_trend.set_facecolor(surface)
        ax3 = self.fig_trend.add_subplot(111)
        ax3.set_facecolor(surface)
        if days:
            ax3.plot(range(len(days)), values, marker='o', markersize=3,
                     linewidth=1.8, color=p["primary"])
            ax3.fill_between(range(len(days)), values, alpha=0.12, color=p["primary"])
            step = max(1, len(days) // 8)
            idx = list(range(0, len(days), step))
            ax3.set_xticks(idx)
            ax3.set_xticklabels([days[i].strftime("%m/%d") for i in idx],
                                rotation=45, fontsize=8, ha="right")
        ax3.set_facecolor(surface)
        ax3.spines[['top', 'right']].set_visible(False)
        ax3.spines[['left', 'bottom']].set_color(p["border"])
        ax3.tick_params(labelsize=8, colors=text_color)
        ax3.grid(axis='y', color=p["border"], linewidth=0.6, alpha=0.6)
        self.fig_trend.tight_layout()
        self.canvas_trend.draw()

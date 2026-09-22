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

from database.models import (ServiceRecord, ServiceRecordTask, Task, Technician,
                             SiteDailyActivity, DEPT_IT, DEPT_SITE)
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
            QLabel {{ color: white; background: transparent; }}
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

        # ---- نوار انتخاب بازه‌ی زمانی ----
        filter_bar = QHBoxLayout()
        self.cmb_period = QComboBox()
        for label, key in [
            ("۳۰ روز اخیر", "last30"), ("۷ روز اخیر", "last7"),
            ("این هفته", "this_week"), ("این ماه", "this_month"),
            ("ماه گذشته", "last_month"), ("۹۰ روز اخیر", "last90"),
            ("همه‌ی زمان‌ها", "all"), ("بازه‌ی دلخواه", "custom"),
        ]:
            self.cmb_period.addItem(label, key)
        self.cmb_period.currentIndexChanged.connect(self._period_changed)

        self.date_from = QDateEdit(); self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy/MM/dd")
        self.date_from.setDate(QDate.currentDate().addDays(-29)); self.date_from.setEnabled(False)
        self.date_from.dateChanged.connect(self.refresh_dashboard)
        self.date_to = QDateEdit(); self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy/MM/dd")
        self.date_to.setDate(QDate.currentDate()); self.date_to.setEnabled(False)
        self.date_to.dateChanged.connect(self.refresh_dashboard)

        filter_bar.addWidget(QLabel("بازه‌ی نمودارها:"))
        filter_bar.addWidget(self.cmb_period)
        filter_bar.addWidget(QLabel("از:")); filter_bar.addWidget(self.date_from)
        filter_bar.addWidget(QLabel("تا:")); filter_bar.addWidget(self.date_to)
        filter_bar.addStretch()
        main_layout.addLayout(filter_bar)

        # ---- کارت‌های KPI (IT / نام‌دار / سایت جدا از هم) ----
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(15)
        self.card_it = StatCard("خدمات واحد IT", "0", "در بازه‌ی انتخابی", "#0284C7")
        self.card_named = StatCard("خدمات نام‌دار", "0", "ارتقا/اسمبل/نصب ویندوز و ...", "#7C3AED")
        self.card_site = StatCard("فعالیت واحد سایت", "0", "ردیف‌های گزارش روزانه‌ی سایت", "#0D9488")
        self.card_techs = StatCard("کارشناسان فعال", "0", "آماده ارائه خدمت", "#D97706")
        for c in (self.card_it, self.card_named, self.card_site, self.card_techs):
            kpi_layout.addWidget(c)
        main_layout.addLayout(kpi_layout)

        # ---- نمودارها ----
        grid = QGridLayout()
        grid.setSpacing(15)

        self.fig_tech = Figure(figsize=(5, 2.8)); self.canvas_tech = FigureCanvas(self.fig_tech)
        self.canvas_tech.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        grid.addWidget(self._chart_box("عملکرد کارشناسان (IT + سایت)", self.canvas_tech), 0, 0)

        self.fig_it = Figure(figsize=(5, 2.8)); self.canvas_it = FigureCanvas(self.fig_it)
        self.canvas_it.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        grid.addWidget(self._chart_box("بیشترین خدمات IT (۱۰ مورد برتر)", self.canvas_it), 0, 1)

        self.fig_named = Figure(figsize=(5, 2.8)); self.canvas_named = FigureCanvas(self.fig_named)
        self.canvas_named.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        grid.addWidget(self._chart_box("خدمات نام‌دار به تفکیک نوع", self.canvas_named), 1, 0)

        self.fig_site = Figure(figsize=(5, 2.8)); self.canvas_site = FigureCanvas(self.fig_site)
        self.canvas_site.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        grid.addWidget(self._chart_box("فعالیت واحد سایت به تفکیک بستر", self.canvas_site), 1, 1)

        self.fig_trend = Figure(figsize=(10, 2.6)); self.canvas_trend = FigureCanvas(self.fig_trend)
        self.canvas_trend.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        grid.addWidget(self._chart_box("روند روزانه (IT و سایت)", self.canvas_trend), 2, 0, 1, 2)

        for r in (0, 1, 2):
            grid.setRowStretch(r, 1)
        main_layout.addLayout(grid, stretch=1)

    def _chart_box(self, title: str, canvas: QWidget) -> QFrame:
        container = QFrame(); container.setObjectName("Card")
        layout = QVBoxLayout(container); layout.setContentsMargins(14, 12, 14, 12)
        lbl = QLabel(title); lbl.setObjectName("SectionTitle")
        layout.addWidget(lbl); layout.addWidget(canvas)
        return container

    # ------------------------------------------------------- بازه‌ی زمانی
    def _period_changed(self):
        is_custom = self.cmb_period.currentData() == "custom"
        self.date_from.setEnabled(is_custom); self.date_to.setEnabled(is_custom)
        self.refresh_dashboard()

    def _chart_range(self):
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
            start = self.date_from.date().toPython(); end = self.date_to.date().toPython()
        elif key == "all":
            first = self.db.query(func.min(ServiceRecord.report_date)).scalar()
            first_site = self.db.query(func.min(SiteDailyActivity.report_date)).scalar()
            candidates = [d for d in (first, first_site) if d]
            start = min(candidates) if candidates else today - timedelta(days=29)
            end = today
        else:
            start, end = today - timedelta(days=29), today
        if end < start:
            start, end = end, start
        if (end - start).days > 180:
            start = end - timedelta(days=180)
        return start, end

    # --------------------------------------------------------- کوئری‌ها
    def _it_records(self, q):
        """فقط رکوردهای واحد IT (رکوردهای قدیمیِ سایت کنار گذاشته می‌شوند)."""
        return q.filter(func.coalesce(ServiceRecord.department, DEPT_IT) != DEPT_SITE)

    def _it_qty(self, start, end, named=None):
        q = (self.db.query(func.sum(ServiceRecordTask.quantity))
             .join(ServiceRecord, ServiceRecord.id == ServiceRecordTask.service_record_id)
             .filter(ServiceRecord.report_date >= start, ServiceRecord.report_date <= end))
        q = self._it_records(q)
        if named is True:
            q = q.filter(ServiceRecordTask.person_name.isnot(None),
                         ServiceRecordTask.person_name != "")
        elif named is False:
            q = q.filter((ServiceRecordTask.person_name.is_(None)) |
                         (ServiceRecordTask.person_name == ""))
        return int(q.scalar() or 0)

    def _named_count(self, start, end):
        q = (self.db.query(func.count(ServiceRecordTask.id))
             .join(ServiceRecord, ServiceRecord.id == ServiceRecordTask.service_record_id)
             .filter(ServiceRecord.report_date >= start, ServiceRecord.report_date <= end,
                     ServiceRecordTask.person_name.isnot(None),
                     ServiceRecordTask.person_name != ""))
        return int(self._it_records(q).scalar() or 0)

    def _site_count(self, start, end):
        return int(self.db.query(func.count(SiteDailyActivity.id))
                   .filter(SiteDailyActivity.report_date >= start,
                           SiteDailyActivity.report_date <= end).scalar() or 0)

    # --------------------------------------------------------- بازآوری
    def refresh_dashboard(self):
        start, end = self._chart_range()
        p = theme.palette
        surface = p["surface"]; text_color = p["text"]

        # ---- کارت‌ها ----
        self.card_it.lbl_value.setText(str(self._it_qty(start, end)))
        self.card_named.lbl_value.setText(str(self._named_count(start, end)))
        self.card_site.lbl_value.setText(str(self._site_count(start, end)))
        self.card_techs.lbl_value.setText(
            str(self.db.query(Technician).filter_by(is_active=True).count()))

        def hbar(fig, canvas, pairs, color):
            fig.clear(); fig.set_facecolor(surface)
            ax = fig.add_subplot(111); ax.set_facecolor(surface)
            if pairs:
                labels = [str(k) for k, _ in pairs]
                values = [int(v or 0) for _, v in pairs]
                bars = ax.barh(labels, values, color=color, height=0.6)
                ax.bar_label(bars, padding=3, fontsize=8, color=text_color)
                ax.invert_yaxis()
                ax.margins(x=0.15)
            else:
                ax.text(0.5, 0.5, "داده‌ای در این بازه نیست", ha="center", va="center",
                        color=text_color, transform=ax.transAxes)
            ax.spines[['top', 'right', 'left', 'bottom']].set_visible(False)
            ax.tick_params(left=False, bottom=False, labelbottom=False,
                           labelsize=9, colors=text_color)
            fig.tight_layout(); canvas.draw()

        # ---- ۱: عملکرد کارشناسان (IT + سایت) ----
        it_tech = (self.db.query(Technician.full_name, func.sum(ServiceRecordTask.quantity))
                   .join(ServiceRecord, ServiceRecord.technician_id == Technician.id)
                   .join(ServiceRecordTask, ServiceRecord.id == ServiceRecordTask.service_record_id)
                   .filter(ServiceRecord.report_date >= start, ServiceRecord.report_date <= end))
        it_tech = self._it_records(it_tech).group_by(Technician.id, Technician.full_name).all()
        combined = {}
        for name, qty in it_tech:
            combined[name or "نامشخص"] = combined.get(name or "نامشخص", 0) + int(qty or 0)
        site_tech = (self.db.query(Technician.full_name, func.count(SiteDailyActivity.id))
                     .join(SiteDailyActivity, SiteDailyActivity.technician_id == Technician.id)
                     .filter(SiteDailyActivity.report_date >= start,
                             SiteDailyActivity.report_date <= end)
                     .group_by(Technician.id, Technician.full_name).all())
        for name, cnt in site_tech:
            combined[name or "نامشخص"] = combined.get(name or "نامشخص", 0) + int(cnt or 0)
        top_tech = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)[:8]
        hbar(self.fig_tech, self.canvas_tech, top_tech, p["primary"])

        # ---- ۲: بیشترین خدمات IT (شمارشی، بدون نام‌دارها) ----
        it_tasks = (self.db.query(Task.title, func.sum(ServiceRecordTask.quantity))
                    .join(ServiceRecordTask, Task.id == ServiceRecordTask.task_id)
                    .join(ServiceRecord, ServiceRecord.id == ServiceRecordTask.service_record_id)
                    .filter(ServiceRecord.report_date >= start, ServiceRecord.report_date <= end,
                            (ServiceRecordTask.person_name.is_(None)) |
                            (ServiceRecordTask.person_name == "")))
        it_tasks = (self._it_records(it_tasks).group_by(Task.title)
                    .order_by(func.sum(ServiceRecordTask.quantity).desc()).limit(10).all())
        hbar(self.fig_it, self.canvas_it, it_tasks, "#2563EB")

        # ---- ۳: خدمات نام‌دار به تفکیک نوع ----
        named = (self.db.query(Task.title, func.count(ServiceRecordTask.id))
                 .join(ServiceRecordTask, Task.id == ServiceRecordTask.task_id)
                 .join(ServiceRecord, ServiceRecord.id == ServiceRecordTask.service_record_id)
                 .filter(ServiceRecord.report_date >= start, ServiceRecord.report_date <= end,
                         ServiceRecordTask.person_name.isnot(None),
                         ServiceRecordTask.person_name != ""))
        named = (self._it_records(named).group_by(Task.title)
                 .order_by(func.count(ServiceRecordTask.id).desc()).limit(10).all())
        hbar(self.fig_named, self.canvas_named, named, "#7C3AED")

        # ---- ۴: فعالیت سایت به تفکیک بستر ----
        site_plat = (self.db.query(SiteDailyActivity.platform, func.count(SiteDailyActivity.id))
                     .filter(SiteDailyActivity.report_date >= start,
                             SiteDailyActivity.report_date <= end)
                     .group_by(SiteDailyActivity.platform)
                     .order_by(func.count(SiteDailyActivity.id).desc()).all())
        hbar(self.fig_site, self.canvas_site, site_plat, "#0D9488")

        # ---- ۵: روند روزانه (IT و سایت) ----
        it_rows = (self.db.query(ServiceRecord.report_date, func.sum(ServiceRecordTask.quantity))
                   .join(ServiceRecordTask, ServiceRecord.id == ServiceRecordTask.service_record_id)
                   .filter(ServiceRecord.report_date >= start, ServiceRecord.report_date <= end))
        it_rows = self._it_records(it_rows).group_by(ServiceRecord.report_date).all()
        it_by_day = {r[0]: int(r[1] or 0) for r in it_rows if r[0] is not None}
        site_rows = (self.db.query(SiteDailyActivity.report_date, func.count(SiteDailyActivity.id))
                     .filter(SiteDailyActivity.report_date >= start,
                             SiteDailyActivity.report_date <= end)
                     .group_by(SiteDailyActivity.report_date).all())
        site_by_day = {r[0]: int(r[1] or 0) for r in site_rows if r[0] is not None}

        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        it_vals = [it_by_day.get(d, 0) for d in days]
        site_vals = [site_by_day.get(d, 0) for d in days]

        self.fig_trend.clear(); self.fig_trend.set_facecolor(surface)
        ax = self.fig_trend.add_subplot(111); ax.set_facecolor(surface)
        if days:
            xs = range(len(days))
            ax.plot(xs, it_vals, marker='o', markersize=3, linewidth=1.8,
                    color=p["primary"], label="IT")
            ax.fill_between(xs, it_vals, alpha=0.10, color=p["primary"])
            ax.plot(xs, site_vals, marker='o', markersize=3, linewidth=1.8,
                    color="#0D9488", label="سایت")
            ax.fill_between(xs, site_vals, alpha=0.10, color="#0D9488")
            step = max(1, len(days) // 8)
            idx = list(range(0, len(days), step))
            ax.set_xticks(idx)
            ax.set_xticklabels([days[i].strftime("%m/%d") for i in idx],
                               rotation=45, fontsize=8, ha="right")
            ax.legend(fontsize=8, facecolor=surface, edgecolor=p["border"], labelcolor=text_color)
        ax.spines[['top', 'right']].set_visible(False)
        ax.spines[['left', 'bottom']].set_color(p["border"])
        ax.tick_params(labelsize=8, colors=text_color)
        ax.grid(axis='y', color=p["border"], linewidth=0.6, alpha=0.6)
        self.fig_trend.tight_layout(); self.canvas_trend.draw()

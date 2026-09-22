"""گزارش‌های واحد سایت — جدا از واحد IT تا کارِ بخش‌ها قاطی نشود.

یک صفحه با دو تبِ داخلی («گزارش روزانه» و «پایش شبکه‌ها») که ردیف‌های ثبت‌شده
را نمایش، فیلتر و به اکسل (همان دو شیتِ فایل مدیریت) خروجی می‌گیرد.

  • حالت شخصی (admin=False): فقط ردیف‌های همان کارشناس.
  • حالت مدیر (admin=True): همه‌ی کارشناسان + فیلترِ کارشناس.
"""
from datetime import datetime, timedelta, date

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                               QComboBox, QDateEdit, QFileDialog, QMessageBox,
                               QAbstractItemView, QTabWidget)
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session

from database.models import (SiteDailyActivity, SiteNetworkStat, Technician,
                             SITE_PLATFORMS)

_PERIODS = [
    ("همه‌ی زمان‌ها", "all"), ("امروز", "today"), ("دیروز", "yesterday"),
    ("۷ روز اخیر", "last7"), ("این هفته", "this_week"), ("هفته‌ی گذشته", "last_week"),
    ("این ماه", "this_month"), ("ماه گذشته", "last_month"), ("۳۰ روز اخیر", "last30"),
    ("بازه‌ی دلخواه", "custom"),
]


def _week_start(d):
    return d - timedelta(days=(d.weekday() - 5) % 7)


class SiteReportsPage(QWidget):
    def __init__(self, db_session: Session, technician=None, admin=False, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.technician = technician
        self.admin = admin
        self.daily_all = []
        self.net_all = []
        self.daily_shown = []
        self.net_shown = []
        self.setup_ui()
        self.load_data()

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("گزارشات واحد سایت" if self.admin else "گزارش‌های سایتِ من")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # --- ردیف فیلترها ---
        bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو در بستر، شرح، وضعیت، توضیحات...")
        self.txt_search.textChanged.connect(self.apply_filters)
        bar.addWidget(QLabel("جستجو:"))
        bar.addWidget(self.txt_search, 2)

        self.cmb_platform = QComboBox()
        self.cmb_platform.addItem("همه‌ی بسترها", None)
        for p in SITE_PLATFORMS:
            self.cmb_platform.addItem(p, p)
        self.cmb_platform.currentIndexChanged.connect(self.apply_filters)
        bar.addWidget(QLabel("بستر:"))
        bar.addWidget(self.cmb_platform, 1)

        self.cmb_tech = None
        if self.admin:
            self.cmb_tech = QComboBox()
            self.cmb_tech.addItem("همه کارشناسان", None)
            self.cmb_tech.currentIndexChanged.connect(self.apply_filters)
            bar.addWidget(QLabel("کارشناس:"))
            bar.addWidget(self.cmb_tech, 1)
        layout.addLayout(bar)

        # --- ردیف بازه‌ی زمانی + عملیات ---
        bar2 = QHBoxLayout()
        self.cmb_period = QComboBox()
        for label, key in _PERIODS:
            self.cmb_period.addItem(label, key)
        self.cmb_period.currentIndexChanged.connect(self._period_changed)

        self.date_from = QDateEdit(); self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy/MM/dd")
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.dateChanged.connect(self.apply_filters); self.date_from.setEnabled(False)

        self.date_to = QDateEdit(); self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy/MM/dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self.apply_filters); self.date_to.setEnabled(False)

        bar2.addWidget(QLabel("بازه‌ی زمانی:"))
        bar2.addWidget(self.cmb_period)
        bar2.addWidget(QLabel("از:")); bar2.addWidget(self.date_from)
        bar2.addWidget(QLabel("تا:")); bar2.addWidget(self.date_to)
        bar2.addStretch()

        btn_refresh = QPushButton("بروزرسانی")
        btn_refresh.setProperty("variant", "ghost")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.load_data)
        btn_export = QPushButton("خروجی اکسل (همه‌ی نمایش)")
        btn_export.setProperty("variant", "success")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self.export_excel)
        bar2.addWidget(btn_refresh)
        bar2.addWidget(btn_export)
        layout.addLayout(bar2)

        # --- دو تبِ داخلی ---
        self.inner = QTabWidget()
        self.tbl_daily = self._make_table(self._daily_headers())
        self.tbl_net = self._make_table(self._net_headers())
        self.inner.addTab(self._wrap(self.tbl_daily, "lbl_daily"), "گزارش روزانه")
        self.inner.addTab(self._wrap(self.tbl_net, "lbl_net"), "پایش شبکه‌ها")
        layout.addWidget(self.inner, 1)

    def _wrap(self, table, label_attr):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addWidget(table, 1)
        lbl = QLabel("")
        lbl.setObjectName("Muted")
        setattr(self, label_attr, lbl)
        lay.addWidget(lbl)
        return w

    def _make_table(self, headers):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        header = t.horizontalHeader()
        for i in range(len(headers) - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(len(headers) - 1, QHeaderView.Stretch)
        return t

    def _daily_headers(self):
        base = ["ردیف", "تاریخ"]
        if self.admin:
            base.append("کارشناس")
        return base + ["نام بستر", "نوع فعالیت", "شرح کار انجام‌شده", "وضعیت", "توضیحات"]

    def _net_headers(self):
        base = ["ردیف", "تاریخ"]
        if self.admin:
            base.append("کارشناس")
        return base + ["نام بستر", "دنبال‌کننده/عضو", "بازدید", "تعامل", "پست",
                       "استوری", "رشد", "وضعیت صفحه", "توضیحات"]

    # ------------------------------------------------------------ داده‌ها
    def load_data(self):
        if self.admin and self.cmb_tech is not None:
            self.cmb_tech.blockSignals(True)
            current = self.cmb_tech.currentData()
            self.cmb_tech.clear()
            self.cmb_tech.addItem("همه کارشناسان", None)
            for t in self.db.query(Technician).filter_by(is_active=True).all():
                self.cmb_tech.addItem(t.full_name, t.id)
            idx = self.cmb_tech.findData(current)
            if idx >= 0:
                self.cmb_tech.setCurrentIndex(idx)
            self.cmb_tech.blockSignals(False)

        dq = self.db.query(SiteDailyActivity)
        nq = self.db.query(SiteNetworkStat)
        if not self.admin and self.technician is not None:
            dq = dq.filter(SiteDailyActivity.technician_id == self.technician.id)
            nq = nq.filter(SiteNetworkStat.technician_id == self.technician.id)
        self.daily_all = dq.order_by(SiteDailyActivity.report_date.desc(),
                                     SiteDailyActivity.id.desc()).all()
        self.net_all = nq.order_by(SiteNetworkStat.report_date.desc(),
                                   SiteNetworkStat.id.desc()).all()
        self.apply_filters()

    def _period_changed(self):
        is_custom = self.cmb_period.currentData() == "custom"
        self.date_from.setEnabled(is_custom)
        self.date_to.setEnabled(is_custom)
        self.apply_filters()

    def _date_range(self):
        key = self.cmb_period.currentData()
        today = datetime.now().date()
        if key == "all":
            return None
        if key == "today":
            return today, today
        if key == "yesterday":
            y = today - timedelta(days=1); return y, y
        if key == "last7":
            return today - timedelta(days=6), today
        if key == "last30":
            return today - timedelta(days=29), today
        if key == "this_week":
            return _week_start(today), today
        if key == "last_week":
            ws = _week_start(today) - timedelta(days=7)
            return ws, ws + timedelta(days=6)
        if key == "this_month":
            return today.replace(day=1), today
        if key == "last_month":
            first_this = today.replace(day=1)
            last_prev = first_this - timedelta(days=1)
            return last_prev.replace(day=1), last_prev
        if key == "custom":
            return self.date_from.date().toPython(), self.date_to.date().toPython()
        return None

    def _match(self, row, words, platform, tech_id, rng):
        if platform and (row.platform or "") != platform:
            return False
        if tech_id and row.technician_id != tech_id:
            return False
        if rng and row.report_date is not None and not (rng[0] <= row.report_date <= rng[1]):
            return False
        if words:
            text = self._searchable(row).lower()
            if not all(w in text for w in words):
                return False
        return True

    @staticmethod
    def _searchable(row):
        parts = [row.technician_name_snapshot or "", row.platform or "",
                 (row.report_date.strftime("%Y/%m/%d") if row.report_date else ""),
                 getattr(row, "activity_type", "") or "",
                 getattr(row, "description", "") or "",
                 getattr(row, "status", "") or "",
                 getattr(row, "growth", "") or "",
                 getattr(row, "page_status", "") or "",
                 row.note or ""]
        return " ".join(parts)

    def apply_filters(self, *_):
        query = self.txt_search.text().strip().lower()
        words = query.split() if query else []
        platform = self.cmb_platform.currentData()
        tech_id = self.cmb_tech.currentData() if (self.admin and self.cmb_tech) else None
        rng = self._date_range()

        self.daily_shown = [r for r in self.daily_all
                            if self._match(r, words, platform, tech_id, rng)]
        self.net_shown = [r for r in self.net_all
                          if self._match(r, words, platform, tech_id, rng)]
        self._fill_daily()
        self._fill_net()

    def _dt(self, d):
        return d.strftime("%Y/%m/%d") if d else "-"

    def _set_row(self, table, row, values):
        for col, val in enumerate(values):
            item = QTableWidgetItem("-" if val in (None, "") else str(val))
            last = (col == len(values) - 1)
            item.setTextAlignment((Qt.AlignLeft if last else Qt.AlignCenter) | Qt.AlignVCenter)
            table.setItem(row, col, item)

    def _fill_daily(self):
        t = self.tbl_daily
        t.setRowCount(len(self.daily_shown))
        for row, r in enumerate(self.daily_shown):
            vals = [row + 1, self._dt(r.report_date)]
            if self.admin:
                vals.append(r.technician_name_snapshot or "-")
            vals += [r.platform, r.activity_type, r.description, r.status, r.note]
            self._set_row(t, row, vals)
        self.lbl_daily.setText(f"تعداد ردیف‌های گزارش روزانه: {len(self.daily_shown)}")

    def _fill_net(self):
        t = self.tbl_net
        t.setRowCount(len(self.net_shown))
        for row, r in enumerate(self.net_shown):
            vals = [row + 1, self._dt(r.report_date)]
            if self.admin:
                vals.append(r.technician_name_snapshot or "-")
            vals += [r.platform, r.followers, r.impressions, r.engagement,
                     r.posts, r.stories, r.growth, r.page_status, r.note]
            self._set_row(t, row, vals)
        self.lbl_net.setText(f"تعداد ردیف‌های پایش شبکه‌ها: {len(self.net_shown)}")

    # ------------------------------------------------------------ خروجی
    def export_excel(self):
        if not self.daily_shown and not self.net_shown:
            QMessageBox.warning(self, "خطا", "ردیفی برای خروجی گرفتن وجود ندارد.")
            return
        default = "Site_Reports.xlsx"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل اکسل", default, "Excel Files (*.xlsx)")
        if not filepath:
            return
        from reports.site_excel_exporter import export_site_to_excel
        try:
            export_site_to_excel(filepath, self.daily_shown, self.net_shown,
                                 technician=self.technician if not self.admin else None)
            QMessageBox.information(self, "موفق", f"فایل اکسل ذخیره شد:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ایجاد فایل اکسل:\n{str(e)}")

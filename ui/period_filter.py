"""انتخاب بازه‌ی زمانی برای صفحه‌های «کارهای شاخص».

همان گزینه‌ها و همان تعریفِ «شروع هفته = شنبه» که صفحه‌های گزارش موجود دارند.
صفحه‌های قدیمی عمداً دست نخورده‌اند (منطق بازه‌شان تکراری است ولی refactor نشد).
"""
from datetime import date, timedelta

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox
from PySide6.QtCore import QDate, Signal
from ui.date_edit import JalaliDateEdit
from utils import jalali

PERIODS = [
    ("همه‌ی زمان‌ها", "all"), ("امروز", "today"), ("دیروز", "yesterday"),
    ("۷ روز اخیر", "last7"), ("این هفته", "this_week"), ("هفته‌ی گذشته", "last_week"),
    ("این ماه", "this_month"), ("ماه گذشته", "last_month"), ("۳۰ روز اخیر", "last30"),
    ("بازه‌ی دلخواه", "custom"),
]


def week_start(d):
    """شنبه‌ی همان هفته."""
    return d - timedelta(days=(d.weekday() - 5) % 7)


def period_range(key, today, date_from=None, date_to=None):
    """(از, تا) شاملِ دو سر، یا None برای «همه‌ی زمان‌ها»."""
    if key == "today":
        return today, today
    if key == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    if key == "last7":
        return today - timedelta(days=6), today
    if key == "last30":
        return today - timedelta(days=29), today
    if key == "this_week":
        return week_start(today), today
    if key == "last_week":
        ws = week_start(today) - timedelta(days=7)
        return ws, ws + timedelta(days=6)
    if key == "this_month":
        return jalali.month_start(today), today
    if key == "last_month":
        return jalali.prev_month_range(today)
    if key == "custom" and date_from and date_to:
        return (date_from, date_to) if date_from <= date_to else (date_to, date_from)
    return None


class PeriodFilter(QWidget):
    """کشوییِ بازه + دو تاریخ از/تا (فقط در «بازه‌ی دلخواه» فعال)."""

    changed = Signal()

    def __init__(self, default="this_month", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.combo = QComboBox()
        for label, key in PERIODS:
            self.combo.addItem(label, key)
        self.date_from = self._date_edit(QDate.currentDate().addDays(-30))
        self.date_to = self._date_edit(QDate.currentDate())
        self.lbl_from = QLabel("از:")
        self.lbl_to = QLabel("تا:")

        layout.addWidget(QLabel("بازه‌ی زمانی:"))
        layout.addWidget(self.combo)
        layout.addWidget(self.lbl_from)
        layout.addWidget(self.date_from)
        layout.addWidget(self.lbl_to)
        layout.addWidget(self.date_to)

        self.set_key(default)
        self.combo.currentIndexChanged.connect(self._on_key_changed)

    def _date_edit(self, qdate):
        w = JalaliDateEdit()
        w.setCalendarPopup(True)
        w.setDisplayFormat("yyyy/MM/dd")
        w.setDate(qdate)
        w.setEnabled(False)
        w.dateChanged.connect(lambda *_: self.changed.emit())
        return w

    def key(self):
        return self.combo.currentData()

    def set_key(self, key):
        idx = self.combo.findData(key)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self._sync_enabled()

    def _sync_enabled(self):
        """تاریخ‌ها فقط در «بازه‌ی دلخواه» قابل تغییرند؛ در بقیه‌ی گزینه‌ها همان بازه‌ای
        را نشان می‌دهند که واقعاً اعمال می‌شود (نه یک تاریخ ثابتِ قدیمی)."""
        key = self.key()
        custom = key == "custom"
        self.date_from.setEnabled(custom)
        self.date_to.setEnabled(custom)
        if not custom:
            rng = period_range(key, date.today())
            if rng is not None:
                for edit, value in zip((self.date_from, self.date_to), rng):
                    edit.blockSignals(True)
                    edit.setDate(QDate(value.year, value.month, value.day))
                    edit.blockSignals(False)
        # «همه‌ی زمان‌ها» تاریخی ندارد؛ نشان دادن از/تا فقط گمراه‌کننده است
        show_dates = key != "all"
        for w in (self.lbl_from, self.date_from, self.lbl_to, self.date_to):
            w.setVisible(show_dates)

    def _on_key_changed(self, *_):
        self._sync_enabled()
        self.changed.emit()

    def date_range(self):
        return period_range(self.key(), date.today(),
                            self.date_from.date().toPython(), self.date_to.date().toPython())

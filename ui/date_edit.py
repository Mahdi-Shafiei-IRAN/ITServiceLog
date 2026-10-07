"""کادر انتخاب تاریخ شمسی — همان QDateEdit با تقویم جلالی.

API دقیقاً مثل QDateEdit است (date() / setDate() / dateChanged همه میلادی می‌مانند)،
فقط متن کادر و تقویم بازشونده شمسی‌اند و هفته از شنبه شروع می‌شود.
"""
from PySide6.QtWidgets import QDateEdit, QCalendarWidget
from PySide6.QtCore import Qt

from utils import jalali


class JalaliDateEdit(QDateEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendar(jalali.calendar())
        self.setDisplayFormat("yyyy/MM/dd")

    def setCalendarPopup(self, enable):
        super().setCalendarPopup(enable)
        popup = self.calendarWidget() if enable else None
        if popup is not None:
            popup.setCalendar(jalali.calendar())
            popup.setFirstDayOfWeek(Qt.Saturday)
            popup.setHorizontalHeaderFormat(QCalendarWidget.SingleLetterDayNames)
            # تعطیلی جمعه است، نه شنبه/یکشنبه‌ی پیش‌فرض Qt
            holiday = popup.weekdayTextFormat(Qt.Sunday)
            normal = popup.weekdayTextFormat(Qt.Monday)
            popup.setWeekdayTextFormat(Qt.Saturday, normal)
            popup.setWeekdayTextFormat(Qt.Sunday, normal)
            popup.setWeekdayTextFormat(Qt.Friday, holiday)

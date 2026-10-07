"""تقویم شمسی (جلالی) برای نمایش و ورود تاریخ‌ها.

دیتابیس همچنان تاریخ میلادی (Date) نگه می‌دارد؛ فقط نمایش، ورودی و بازه‌های
«این ماه / ماه گذشته» شمسی‌اند. تبدیل‌ها با تقویم Jalali خود Qt انجام می‌شود تا
متن جدول‌ها، اکسل و کادرهای انتخاب تاریخ همیشه یکی باشند.
"""
from datetime import date, datetime, timedelta

from PySide6.QtCore import QCalendar, QDate

_CAL = QCalendar(QCalendar.System.Jalali)


def calendar():
    return _CAL


def _as_date(d):
    return d.date() if isinstance(d, datetime) else d


def parts(d):
    """(سال, ماه, روز) شمسیِ یک تاریخ میلادی."""
    d = _as_date(d)
    p = _CAL.partsFromDate(QDate(d.year, d.month, d.day))
    return p.year, p.month, p.day


def to_gregorian(jy, jm, jd):
    return _CAL.dateFromParts(jy, jm, jd).toPython()


def fmt(d, sep="/"):
    """«1405/07/15» یا «-» برای تاریخ خالی."""
    if not d:
        return "-"
    y, m, day = parts(d)
    return f"{y:04d}{sep}{m:02d}{sep}{day:02d}"


def fmt_md(d):
    """«07/15» برای برچسب محور نمودارها."""
    _, m, day = parts(d)
    return f"{m:02d}/{day:02d}"


def range_text(rng):
    return f"{fmt(rng[0])} تا {fmt(rng[1])}"


def month_start(d):
    """اولین روزِ ماه شمسیِ همان تاریخ (به میلادی)."""
    y, m, _ = parts(d)
    return to_gregorian(y, m, 1)


def prev_month_range(d):
    """(اول, آخر) ماه شمسیِ قبل."""
    last_prev = month_start(d) - timedelta(days=1)
    return month_start(last_prev), last_prev


def today_text():
    return fmt(date.today())

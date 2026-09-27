"""منطق کسب‌وکارِ «کارهای شاخص IT» — مستقل از رابط کاربری.

هم صفحه‌ها و هم خروجی اکسل از همین توابع استفاده می‌کنند تا عددها همیشه یکی باشند.
rng همه‌جا یا None (همه‌ی زمان‌ها) است یا تاپل (date_from, date_to) شاملِ دو سر.
"""
from datetime import datetime

from database.models import (KeyActivity, KeyActivityUpdate, KEY_STATUSES,
                             KEY_STATUS_DONE, KEY_STATUS_IN_PROGRESS, KEY_STATUS_CANCELLED,
                             KEY_CATEGORIES_DEFAULT)

UNKNOWN = "نامشخص"
_CLOSED = (KEY_STATUS_DONE, KEY_STATUS_CANCELLED)


def _in_range(d, rng):
    return rng is None or (d is not None and rng[0] <= d <= rng[1])


def is_closed_status(status):
    """وضعیت بسته است؟ («انجام شد» یا «لغو شد»)."""
    return status in _CLOSED


def in_period(activity, rng):
    """کار با بازه هم‌پوشانی دارد؟

    تاریخ اتمام فقط برای وضعیت‌های بسته (انجام‌شده/لغوشده) معنا دارد؛ کارِ باز
    حتی اگر تاریخ اتمامِ دستی هم داشته باشد، تا امروز باز در نظر گرفته می‌شود
    (تا از بازه‌های بعدی پنهان نشود).
    """
    if rng is None:
        return True
    if activity.start_date is None or activity.start_date > rng[1]:
        return False
    if not is_closed_status(activity.status):
        return True
    return activity.end_date is None or activity.end_date >= rng[0]


def updates_in_period(activities, rng):
    """به‌روزرسانی‌هایی که تاریخشان داخل بازه است (قدیمی به جدید)."""
    ups = [u for a in activities for u in a.updates if _in_range(u.update_date, rng)]
    return sorted(ups, key=lambda u: (u.update_date, u.id or 0))


def _count(values):
    out = {}
    for value in values:
        key = value or UNKNOWN
        out[key] = out.get(key, 0) + 1
    return out


def summarize(activities, rng):
    """عددهای نوار خلاصه و شیت جمع‌بندی (فقط روی کارهای داخل بازه)."""
    acts = [a for a in activities if in_period(a, rng)]
    return {
        "total": len(acts),
        "done_in_period": sum(1 for a in acts
                              if a.status == KEY_STATUS_DONE and _in_range(a.end_date, rng)),
        "started_in_period": sum(1 for a in acts if _in_range(a.start_date, rng)),
        "in_progress": sum(1 for a in acts if a.status == KEY_STATUS_IN_PROGRESS),
        "updates_in_period": len(updates_in_period(acts, rng)),
        "by_status": _count(a.status for a in acts),
        "by_category": _count(a.category for a in acts),
        "by_priority": _count(a.priority for a in acts),
    }


def apply_status(activity, status, today):
    """تغییر وضعیت با قاعده‌ی تاریخ اتمام.

    ورود به یک وضعیت بسته (انجام‌شده یا لغوشده) ← (اگر خالی بود) تاریخ اتمام = today؛
    فقط «انجام شد» علاوه بر آن پیشرفت را هم ۱۰۰ می‌کند (لغو کردن پیشرفت را دست نمی‌زند).
    خروج از یک وضعیت بسته به یک وضعیت باز ← تاریخ اتمام پاک می‌شود.
    جابه‌جایی بین دو وضعیت بسته (انجام‌شده ⇄ لغوشده) تاریخ اتمام را حفظ می‌کند.
    جابه‌جایی بین دو وضعیت باز اصلاً تاریخ اتمام را دست نمی‌زند.
    """
    was_closed = is_closed_status(activity.status)
    activity.status = status
    if is_closed_status(status):
        if status == KEY_STATUS_DONE:
            activity.progress = 100
        if activity.end_date is None:
            activity.end_date = today
    elif was_closed:
        activity.end_date = None


def add_update(db, activity, update_date, text, progress=None, status=None, author=""):
    """یک به‌روزرسانی ثبت و پیشرفت/وضعیت کار را جلو می‌برد. commit نمی‌کند."""
    text = (text or "").strip()
    if not text:
        raise ValueError("متن به‌روزرسانی الزامی است.")
    if progress is not None and not 0 <= progress <= 100:
        raise ValueError("درصد پیشرفت باید بین ۰ تا ۱۰۰ باشد.")
    if status is not None and status not in KEY_STATUSES:
        raise ValueError(f"وضعیت نامعتبر است: {status}")

    if progress is not None:
        activity.progress = progress
    if status is not None and status != activity.status:
        apply_status(activity, status, update_date)
    activity.updated_at = datetime.now()

    update = KeyActivityUpdate(update_date=update_date, text=text,
                               progress=activity.progress, status=activity.status,
                               author_name_snapshot=author)
    activity.updates.append(update)
    db.add(update)
    return update


def validate_activity(title, start_date, end_date, progress):
    """پیام‌های خطای فرم کار شاخص (لیست خالی یعنی معتبر)."""
    errors = []
    if not (title or "").strip():
        errors.append("عنوان کار الزامی است.")
    if start_date is None:
        errors.append("تاریخ شروع الزامی است.")
    elif end_date is not None and end_date < start_date:
        errors.append("تاریخ اتمام نمی‌تواند قبل از تاریخ شروع باشد.")
    if progress is not None and not 0 <= progress <= 100:
        errors.append("درصد پیشرفت باید بین ۰ تا ۱۰۰ باشد.")
    return errors


def category_suggestions(db):
    """دسته‌های پیش‌فرض (به همان ترتیب) + دسته‌هایی که قبلاً ثبت شده‌اند (مرتب، بدون تکرار)."""
    out = list(KEY_CATEGORIES_DEFAULT)
    used = {(c or "").strip() for (c,) in db.query(KeyActivity.category).distinct()}
    out.extend(sorted(c for c in used if c and c not in out))
    return out


def last_update_date(activity):
    dates = [u.update_date for u in activity.updates if u.update_date]
    return max(dates) if dates else None


def timeline(activity):
    """به‌روزرسانی‌های یک کار، جدیدترین اول."""
    return sorted(activity.updates, key=lambda u: (u.update_date, u.id or 0), reverse=True)


def _search_text(activity):
    parts = [activity.title, activity.category, activity.description, activity.result,
             activity.technician_name_snapshot]
    parts += [u.text for u in activity.updates]
    return " ".join(p for p in parts if p).lower()


def filter_activities(activities, rng=None, status=None, category=None, priority=None,
                      owner_id=None, words=()):
    """فیلترهای صفحه؛ هر پارامتر None/خالی یعنی «همه»."""
    words = [w.lower() for w in words if w]
    out = []
    for a in activities:
        if not in_period(a, rng):
            continue
        if status and a.status != status:
            continue
        if category and (a.category or "") != category:
            continue
        if priority and a.priority != priority:
            continue
        if owner_id and a.technician_id != owner_id:
            continue
        if words:
            text = _search_text(a)
            if not all(w in text for w in words):
                continue
        out.append(a)
    return out


def sort_activities(activities):
    """کارهای باز اول، سپس بر اساس آخرین تغییر (جدیدترین اول)."""
    by_recent = sorted(activities, key=lambda a: a.updated_at or a.created_at or datetime.min,
                       reverse=True)
    return sorted(by_recent, key=lambda a: a.status in _CLOSED)

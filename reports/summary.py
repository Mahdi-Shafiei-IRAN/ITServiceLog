"""توابع کمکی برای خلاصه‌سازی برگه‌های گزارش روزانه."""
from database.models import DEPT_LABELS


def dept_label(record):
    return DEPT_LABELS.get(record.department, record.department or "-")


def record_date(record):
    """تاریخ گزارش؛ اگر ثبت نشده بود از زمان ایجاد استفاده می‌شود."""
    if getattr(record, "report_date", None):
        return record.report_date
    return record.created_at.date() if record.created_at else None


def date_text(record):
    d = record_date(record)
    return d.strftime("%Y/%m/%d") if d else "-"


def counted_lines(record):
    """خطوط شمارشی (خدمات کلی روز)."""
    return [line for line in record.tasks if not line.person_name]


def named_lines(record):
    """خطوط نام‌دار (ارتقا / اسمبل / نصب ویندوز و ...)."""
    return [line for line in record.tasks if line.person_name]


def total_count(record):
    return sum((line.quantity or 1) for line in record.tasks)


def summary_text(record, separator=" | "):
    """خلاصه‌ی یک‌خطی از کل خدمات آن روز، برای نمایش در جدول‌ها و اکسل."""
    parts = []
    for line in counted_lines(record):
        title = line.task.title if line.task else "؟"
        parts.append(f"{title} ×{line.quantity or 1}")

    grouped = {}
    for line in named_lines(record):
        title = line.task.title if line.task else "؟"
        grouped.setdefault(title, []).append(line.person_name)
    for title, names in grouped.items():
        parts.append(f"{title}: {'، '.join(names)}")

    return separator.join(parts) if parts else "-"


def named_text(record):
    grouped = {}
    for line in named_lines(record):
        title = line.task.title if line.task else "؟"
        grouped.setdefault(title, []).append(line.person_name)
    return " | ".join(f"{t}: {'، '.join(n)}" for t, n in grouped.items()) or "-"


def searchable_text(record):
    """متنی که جستجوی جدول‌ها روی آن انجام می‌شود."""
    pieces = [str(record.id), record.technician_name_snapshot or "",
              dept_label(record), date_text(record), record.short_description or ""]
    for line in record.tasks:
        pieces.append(line.task.title if line.task else "")
        pieces.append(line.person_name or "")
        pieces.append(line.person_extension or "")
        pieces.append(line.system_name or "")
        pieces.append(line.note or "")
    return " ".join(pieces).lower()

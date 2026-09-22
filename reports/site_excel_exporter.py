"""خروجی اکسل واحد سایت — دقیقاً با دو شیتِ فایل «گزارش مدیریت».

  1. «گزارش روزانه»  — هر ردیف یک فعالیت (نام بستر، نوع فعالیت، شرح، وضعیت، توضیحات)
  2. «پایش شبکه‌ها» — آمار روزانه‌ی هر بستر (دنبال‌کننده، بازدید، تعامل، پست، ...)

از همان استایل و توابعِ خروجیِ واحد IT استفاده می‌کند تا ظاهر یکدست بماند.
"""
import openpyxl

from reports.excel_exporter import _new_sheet, _write_row


def _dt(d):
    return d.strftime("%Y/%m/%d") if d else "-"


def _num(v):
    return v if v is not None else "-"


def export_site_to_excel(filepath, daily_rows, network_rows,
                         technician=None, date_range=None):
    wb = openpyxl.Workbook()

    # ---------------- شیت ۱: گزارش روزانه ----------------
    ws = _new_sheet(wb, "گزارش روزانه", [
        "ردیف", "تاریخ", "کارشناس", "نام بستر", "نوع فعالیت",
        "شرح کار انجام‌شده", "وضعیت", "توضیحات",
    ], first=True)
    for i, r in enumerate(daily_rows, 1):
        _write_row(ws, i + 1, [
            i,
            _dt(r.report_date),
            r.technician_name_snapshot or "-",
            r.platform or "-",
            r.activity_type or "-",
            r.description or "-",
            r.status or "-",
            r.note or "-",
        ], wrap_from=6)
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 14
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 50
    ws.column_dimensions['H'].width = 32

    # ---------------- شیت ۲: پایش شبکه‌ها ----------------
    ws2 = _new_sheet(wb, "پایش شبکه‌ها", [
        "ردیف", "تاریخ", "کارشناس", "نام بستر",
        "تعداد دنبال‌کننده/عضو", "بازدید/Impression", "تعامل/Engagement",
        "تعداد پست", "تعداد استوری", "رشد نسبت به قبل", "وضعیت صفحه", "توضیحات",
    ])
    for i, r in enumerate(network_rows, 1):
        _write_row(ws2, i + 1, [
            i,
            _dt(r.report_date),
            r.technician_name_snapshot or "-",
            r.platform or "-",
            _num(r.followers),
            _num(r.impressions),
            _num(r.engagement),
            _num(r.posts),
            _num(r.stories),
            r.growth or "-",
            r.page_status or "-",
            r.note or "-",
        ], wrap_from=10)
    ws2.column_dimensions['C'].width = 18
    ws2.column_dimensions['D'].width = 14
    ws2.column_dimensions['E'].width = 18
    ws2.column_dimensions['L'].width = 30

    # ---------------- شیت ۳: جمع‌بندی ----------------
    ws_sum = _new_sheet(wb, "جمع‌بندی", ["عنوان", "مقدار"])
    rows = []
    if technician:
        rows.append(("کارشناس", technician.full_name))
    if date_range:
        rows.append(("بازه‌ی گزارش", f"{date_range[0]} تا {date_range[1]}"))
    rows.append(("تعداد ردیف‌های گزارش روزانه", len(daily_rows)))
    rows.append(("تعداد ردیف‌های پایش شبکه‌ها", len(network_rows)))
    # تفکیک گزارش روزانه بر اساس بستر
    by_platform = {}
    for r in daily_rows:
        key = r.platform or "؟"
        by_platform[key] = by_platform.get(key, 0) + 1
    if by_platform:
        rows.append(("", ""))
        rows.append(("گزارش روزانه به تفکیک بستر", ""))
        rows.extend(sorted(by_platform.items(), key=lambda kv: kv[1], reverse=True))
    for i, (key, value) in enumerate(rows, 2):
        _write_row(ws_sum, i, [key, value], wrap_from=1)
    ws_sum.column_dimensions['A'].width = 40
    ws_sum.column_dimensions['B'].width = 22

    wb.save(filepath)

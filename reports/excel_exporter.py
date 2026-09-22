"""خروجی اکسل گزارش‌های روزانه.

سه شیت تولید می‌شود:
  1. «گزارش روزانه»      — یک ردیف به ازای هر روز/بخش/کارشناس با شرح و مجموع
  2. «تفکیک خدمات»       — یک ردیف به ازای هر خدمت در هر روز، با تعداد
  3. «خدمات نام‌دار»      — ارتقا / اسمبل / نصب ویندوز و ... تک‌تک با نام فرد
"""
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

from reports import summary


def export_named_services_to_excel(filepath, lines, technician=None, date_range=None):
    """خروجی اکسل مخصوصِ «خدمات نام‌دار» (ارتقا/اسمبل/نصب ویندوز و ...).

    lines: لیستی از ServiceRecordTask که person_name دارند (هر ردیف یک مورد).
    """
    wb = openpyxl.Workbook()
    ws = _new_sheet(wb, "خدمات نام‌دار", [
        "ردیف", "تاریخ", "کارشناس", "خدمت", "نام فرد", "داخلی", "سیستم", "توضیح",
    ], first=True)
    for i, line in enumerate(lines, 1):
        rec = line.record
        _write_row(ws, i + 1, [
            i,
            summary.date_text(rec) if rec else "-",
            (rec.technician_name_snapshot if rec else None) or "-",
            line.task.title if line.task else "-",
            line.person_name or "-",
            line.person_extension or "-",
            line.system_name or "-",
            line.note or "-",
        ], wrap_from=4)
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 28
    ws.column_dimensions['E'].width = 22
    ws.column_dimensions['H'].width = 32

    # شیت جمع‌بندی بر اساس نوع خدمت
    ws_sum = _new_sheet(wb, "جمع‌بندی", ["خدمت", "تعداد"])
    totals = {}
    for line in lines:
        title = line.task.title if line.task else "؟"
        totals[title] = totals.get(title, 0) + 1
    rows = []
    if technician:
        rows.append(("کارشناس", technician.full_name))
    if date_range:
        rows.append(("بازه‌ی گزارش", f"{date_range[0]} تا {date_range[1]}"))
    rows.append(("مجموع خدمات نام‌دار", len(lines)))
    rows.append(("", ""))
    rows.extend(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))
    for i, (key, value) in enumerate(rows, 2):
        _write_row(ws_sum, i, [key, value], wrap_from=1)
    ws_sum.column_dimensions['A'].width = 32
    ws_sum.column_dimensions['B'].width = 14

    wb.save(filepath)

HEADER_FILL = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
HEADER_FONT = Font(name="Tahoma", bold=True, color="FFFFFF")
BORDER = Border(left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))


def _new_sheet(wb, title, headers, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.sheet_view.rightToLeft = True
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        cell.border = BORDER
    return ws


def _write_row(ws, row_num, values, wrap_from=1):
    for col_num, value in enumerate(values, 1):
        cell = ws.cell(row=row_num, column=col_num, value=value)
        cell.font = Font(name="Tahoma")
        cell.alignment = Alignment(
            wrap_text=True,
            horizontal="right" if col_num >= wrap_from else "center")
        cell.border = BORDER


def export_records_to_excel(filepath, records, technician=None, date_range=None):
    wb = openpyxl.Workbook()

    # ---------------- شیت ۱: خلاصه‌ی هر روز ----------------
    ws = _new_sheet(wb, "گزارش روزانه", [
        "ردیف", "تاریخ", "بخش", "کارشناس", "داخلی کارشناس",
        "مجموع خدمات", "شرح خدمات روز", "توضیحات"
    ], first=True)
    for i, record in enumerate(records, 1):
        tech_ext = record.technician.internal_extension if record.technician else ""
        _write_row(ws, i + 1, [
            i,
            summary.date_text(record),
            summary.dept_label(record),
            record.technician_name_snapshot or "-",
            tech_ext or "-",
            summary.total_count(record),
            summary.summary_text(record),
            record.short_description or "-",
        ], wrap_from=7)
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['G'].width = 60
    ws.column_dimensions['H'].width = 35

    # ---------------- شیت ۲: تفکیک خدمات ----------------
    ws2 = _new_sheet(wb, "تفکیک خدمات", [
        "ردیف", "تاریخ", "بخش", "کارشناس", "خدمت", "تعداد", "توضیح"
    ])
    row = 2
    for record in records:
        for line in summary.counted_lines(record):
            _write_row(ws2, row, [
                row - 1,
                summary.date_text(record),
                summary.dept_label(record),
                record.technician_name_snapshot or "-",
                line.task.title if line.task else "-",
                line.quantity or 1,
                line.note or "-",
            ], wrap_from=5)
            row += 1
    ws2.column_dimensions['D'].width = 20
    ws2.column_dimensions['E'].width = 40
    ws2.column_dimensions['G'].width = 32

    # ---------------- شیت ۳: خدمات نام‌دار ----------------
    ws3 = _new_sheet(wb, "خدمات نام‌دار", [
        "ردیف", "تاریخ", "بخش", "کارشناس", "خدمت",
        "نام فرد", "داخلی", "توضیح"
    ])
    row = 2
    for record in records:
        for line in summary.named_lines(record):
            _write_row(ws3, row, [
                row - 1,
                summary.date_text(record),
                summary.dept_label(record),
                record.technician_name_snapshot or "-",
                line.task.title if line.task else "-",
                line.person_name or "-",
                line.person_extension or "-",
                line.note or "-",
            ], wrap_from=5)
            row += 1
    ws3.column_dimensions['E'].width = 30
    ws3.column_dimensions['F'].width = 22
    ws3.column_dimensions['H'].width = 32

    # ---------------- شیت خلاصه ----------------
    ws_sum = _new_sheet(wb, "جمع‌بندی", ["عنوان", "مقدار"])
    totals = {}
    for record in records:
        for line in record.tasks:
            title = line.task.title if line.task else "؟"
            totals[title] = totals.get(title, 0) + (line.quantity or 1)

    rows = [
        ("تعداد روزهای گزارش‌شده", len(records)),
        ("مجموع کل خدمات", sum(summary.total_count(r) for r in records)),
    ]
    if technician:
        rows.insert(0, ("کارشناس", technician.full_name))
    if date_range:
        rows.append(("بازه‌ی گزارش", f"{date_range[0]} تا {date_range[1]}"))
    rows.append(("", ""))
    rows.append(("تفکیک بر اساس نوع خدمت", ""))
    rows.extend(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))

    for i, (key, value) in enumerate(rows, 2):
        _write_row(ws_sum, i, [key, value], wrap_from=1)
    ws_sum.column_dimensions['A'].width = 45
    ws_sum.column_dimensions['B'].width = 18

    wb.save(filepath)

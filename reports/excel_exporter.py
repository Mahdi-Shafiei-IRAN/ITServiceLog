import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from datetime import datetime

def export_records_to_excel(filepath, records, technician=None, date_range=None):
    wb = openpyxl.Workbook()
    ws_data = wb.active
    ws_data.title = "گزارش مراجعات"
    ws_data.sheet_view.rightToLeft = True  # Enable RTL for Persian
    
    headers = [
        "ردیف", "تاریخ", "ساعت", "نام مراجعه‌کننده", "داخلی", 
        "نام سیستم", "کارشناس IT", "داخلی کارشناس", "عملیات انجام‌شده", "توضیحات"
    ]
    
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    header_font = Font(name="Tahoma", bold=True, color="FFFFFF")
    border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                    top=Side(style='thin'), bottom=Side(style='thin'))
    
    for col_num, header in enumerate(headers, 1):
        cell = ws_data.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = border

    for row_num, record in enumerate(records, 2):
        tasks_str = " | ".join([t.task.title for t in record.tasks])
        row_data = [
            row_num - 1,
            record.created_at.strftime("%Y/%m/%d"),
            record.created_at.strftime("%H:%M"),
            record.requester_name_snapshot,
            record.requester_extension_snapshot,
            record.system_name_snapshot or "-",
            record.technician_name_snapshot,
            record.technician.internal_extension,
            tasks_str,
            record.short_description or "-"
        ]
        
        for col_num, value in enumerate(row_data, 1):
            cell = ws_data.cell(row=row_num, column=col_num, value=value)
            cell.font = Font(name="Tahoma")
            cell.alignment = Alignment(wrap_text=True, horizontal="right" if col_num > 3 else "center")
            cell.border = border

    ws_data.column_dimensions['D'].width = 20
    ws_data.column_dimensions['F'].width = 20
    ws_data.column_dimensions['I'].width = 40
    ws_data.column_dimensions['J'].width = 40

    if technician:
        ws_summary = wb.create_sheet(title="خلاصه")
        ws_summary.sheet_view.rightToLeft = True
        ws_summary["A1"] = "نام کارشناس:"
        ws_summary["B1"] = technician.full_name
        ws_summary["A2"] = "مجموع مراجعات:"
        ws_summary["B2"] = len(records)
        
        for row in range(1, 3):
            ws_summary[f"A{row}"].font = Font(name="Tahoma", bold=True)
            ws_summary[f"B{row}"].font = Font(name="Tahoma")

    wb.save(filepath)
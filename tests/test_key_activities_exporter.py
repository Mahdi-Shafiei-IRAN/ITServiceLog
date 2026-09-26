from datetime import date

import openpyxl

from database.models import (KeyActivity, KeyActivityUpdate, Technician,
                             KEY_STATUS_DONE, KEY_STATUS_IN_PROGRESS,
                             KEY_PRIORITY_NORMAL, KEY_PRIORITY_TOP)
from reports.key_activities_exporter import (export_key_activities_to_excel,
                                             default_filename, range_label)

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def _acts():
    a1 = KeyActivity(title="راه‌اندازی سرور بکاپ", category="سرور", priority=KEY_PRIORITY_TOP,
                     status=KEY_STATUS_IN_PROGRESS, progress=60, start_date=date(2026, 8, 20),
                     technician_name_snapshot="مدیر IT", description="بکاپ شبانه", result=None)
    a1.updates.append(KeyActivityUpdate(update_date=date(2026, 8, 25), text="خرید استوریج",
                                        progress=20, status=KEY_STATUS_IN_PROGRESS,
                                        author_name_snapshot="مدیر IT"))
    a1.updates.append(KeyActivityUpdate(update_date=date(2026, 9, 10), text="نصب و پیکربندی",
                                        progress=60, status=KEY_STATUS_IN_PROGRESS,
                                        author_name_snapshot="مدیر IT"))
    a2 = KeyActivity(title="رفع قطعی شبکه", category="شبکه", priority=KEY_PRIORITY_NORMAL,
                     status=KEY_STATUS_DONE, progress=100, start_date=date(2026, 9, 5),
                     end_date=date(2026, 9, 5), technician_name_snapshot="مدیر IT")
    return [a1, a2]


def _summary(wb):
    ws = wb["جمع‌بندی"]
    return {ws.cell(row=r, column=1).value: ws.cell(row=r, column=2).value
            for r in range(2, ws.max_row + 1)}


def test_three_sheets_for_a_period(tmp_path):
    path = tmp_path / "k.xlsx"
    export_key_activities_to_excel(str(path), _acts(), SEPT)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["کارهای شاخص", "گزارش پیشرفت", "جمع‌بندی"]

    ws = wb["کارهای شاخص"]
    assert [c.value for c in ws[1]] == ["ردیف", "عنوان", "دسته", "اهمیت", "وضعیت",
                                        "پیشرفت ٪", "شروع", "اتمام", "شرح", "نتیجه"]
    assert ws.max_row == 3
    assert [c.value for c in ws[2]] == [1, "راه‌اندازی سرور بکاپ", "سرور", KEY_PRIORITY_TOP,
                                        KEY_STATUS_IN_PROGRESS, 60, "2026/08/20", "-",
                                        "بکاپ شبانه", "-"]

    ws2 = wb["گزارش پیشرفت"]
    assert [c.value for c in ws2[1]] == ["ردیف", "تاریخ", "عنوان کار", "متن به‌روزرسانی",
                                         "پیشرفت ٪", "وضعیت", "ثبت‌کننده"]
    assert ws2.max_row == 2   # فقط به‌روزرسانیِ داخل شهریور
    assert [c.value for c in ws2[2]] == [1, "2026/09/10", "راه‌اندازی سرور بکاپ",
                                         "نصب و پیکربندی", 60, KEY_STATUS_IN_PROGRESS, "مدیر IT"]

    summary = _summary(wb)
    assert summary["بازه‌ی گزارش"] == "2026/09/01 تا 2026/09/30"
    assert summary["تعداد کارهای شاخص در بازه"] == 2
    assert summary["انجام‌شده در بازه"] == 1
    assert summary["شروع‌شده در بازه"] == 1
    assert summary["در حال انجام"] == 1
    assert summary["تعداد به‌روزرسانی‌ها در بازه"] == 1
    assert summary["سرور"] == 1 and summary["شبکه"] == 1
    assert "ثبت‌کننده" not in summary


def test_owner_column_and_owner_row(tmp_path):
    path = tmp_path / "k.xlsx"
    owner = Technician(full_name="مدیر IT")
    export_key_activities_to_excel(str(path), _acts(), SEPT, owner=owner, show_owner=True)
    wb = openpyxl.load_workbook(path)
    headers = [c.value for c in wb["کارهای شاخص"][1]]
    assert headers[8] == "ثبت‌کننده"
    assert wb["کارهای شاخص"]["I2"].value == "مدیر IT"
    assert _summary(wb)["ثبت‌کننده"] == "مدیر IT"


def test_all_time_export(tmp_path):
    path = tmp_path / "k.xlsx"
    export_key_activities_to_excel(str(path), _acts(), None)
    wb = openpyxl.load_workbook(path)
    assert wb["گزارش پیشرفت"].max_row == 3
    assert _summary(wb)["بازه‌ی گزارش"] == "همه‌ی زمان‌ها"


def test_empty_export_still_has_three_sheets(tmp_path):
    path = tmp_path / "k.xlsx"
    export_key_activities_to_excel(str(path), [], SEPT)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["کارهای شاخص", "گزارش پیشرفت", "جمع‌بندی"]
    assert _summary(wb)["تعداد کارهای شاخص در بازه"] == 0


def test_default_filename_and_range_label():
    assert default_filename(SEPT) == "Key_Activities_2026-09-01_2026-09-30.xlsx"
    assert default_filename(None) == "Key_Activities_All.xlsx"
    assert range_label(None) == "همه‌ی زمان‌ها"
    assert range_label(SEPT) == "2026/09/01 تا 2026/09/30"

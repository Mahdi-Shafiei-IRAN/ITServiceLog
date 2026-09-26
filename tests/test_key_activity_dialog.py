from datetime import date

from PySide6.QtCore import QDate

from database.models import (KeyActivity, KEY_STATUS_DONE, KEY_STATUS_IN_PROGRESS,
                             KEY_PRIORITY_NORMAL)
from ui.key_activity_dialog import KeyActivityDialog


def test_new_activity_is_saved_for_technician(qapp, db, owner, dialogs):
    dlg = KeyActivityDialog(db, owner)
    dlg.txt_title.setText("  راه‌اندازی سرور بکاپ ")
    dlg.cmb_category.setEditText("ذخیره‌سازی")
    dlg.txt_description.setPlainText("بکاپ شبانه‌ی سرورها")
    assert dlg.save() is True
    act = db.query(KeyActivity).one()
    assert act.title == "راه‌اندازی سرور بکاپ"
    assert act.category == "ذخیره‌سازی"
    assert act.description == "بکاپ شبانه‌ی سرورها"
    assert act.result is None
    assert act.technician_id == owner.id
    assert act.technician_name_snapshot == owner.full_name
    assert act.status == KEY_STATUS_IN_PROGRESS
    assert act.priority == KEY_PRIORITY_NORMAL
    assert act.progress == 0
    assert act.start_date == date.today()
    assert act.end_date is None
    assert dlg.activity is act


def test_blank_title_is_rejected(qapp, db, owner, dialogs):
    calls, _ = dialogs
    dlg = KeyActivityDialog(db, owner)
    assert dlg.save() is False
    assert db.query(KeyActivity).count() == 0
    assert calls and calls[0][0] == "warning" and "عنوان کار الزامی است." in calls[0][1]


def test_end_before_start_is_rejected(qapp, db, owner, dialogs):
    dlg = KeyActivityDialog(db, owner)
    dlg.txt_title.setText("کار")
    dlg.date_start.setDate(QDate(2026, 9, 10))
    dlg.chk_has_end.setChecked(True)
    dlg.date_end.setDate(QDate(2026, 9, 1))
    assert dlg.save() is False
    assert db.query(KeyActivity).count() == 0


def test_one_day_checkbox_marks_done_on_start_date(qapp, db, owner, dialogs):
    dlg = KeyActivityDialog(db, owner)
    dlg.txt_title.setText("رفع قطعی شبکه")
    dlg.date_start.setDate(QDate(2026, 9, 20))
    dlg.chk_one_day.setChecked(True)
    vals = dlg.values()
    assert vals["status"] == KEY_STATUS_DONE
    assert vals["progress"] == 100
    assert vals["end_date"] == date(2026, 9, 20)
    assert not dlg.cmb_status.isEnabled()
    dlg.date_start.setDate(QDate(2026, 9, 21))       # تاریخ اتمام دنبال شروع می‌آید
    assert dlg.values()["end_date"] == date(2026, 9, 21)
    dlg.chk_one_day.setChecked(False)
    assert dlg.cmb_status.isEnabled()


def test_switching_to_done_fills_end_date_and_back_clears_it(qapp, db, owner, dialogs):
    dlg = KeyActivityDialog(db, owner)
    dlg.cmb_status.setCurrentText(KEY_STATUS_DONE)
    assert dlg.chk_has_end.isChecked()
    assert dlg.date_end.date().toPython() == date.today()
    assert dlg.spn_progress.value() == 100
    dlg.cmb_status.setCurrentText(KEY_STATUS_IN_PROGRESS)
    assert not dlg.chk_has_end.isChecked()
    assert dlg.values()["end_date"] is None


def test_edit_existing_activity(qapp, db, owner, dialogs):
    act = KeyActivity(technician_id=owner.id, technician_name_snapshot=owner.full_name,
                      title="قدیمی", category="شبکه", start_date=date(2026, 9, 1),
                      status=KEY_STATUS_DONE, progress=100, end_date=date(2026, 9, 3))
    db.add(act)
    db.commit()
    dlg = KeyActivityDialog(db, owner, activity=act)
    assert dlg.chk_one_day is None
    assert dlg.txt_title.text() == "قدیمی"
    assert dlg.cmb_category.currentText() == "شبکه"
    assert dlg.chk_has_end.isChecked()
    assert dlg.date_end.date().toPython() == date(2026, 9, 3)
    dlg.txt_title.setText("جدید")
    assert dlg.save() is True
    db.refresh(act)
    assert act.title == "جدید"
    assert act.end_date == date(2026, 9, 3)
    assert db.query(KeyActivity).count() == 1


def test_category_combo_offers_defaults_and_used(qapp, db, owner, dialogs):
    db.add(KeyActivity(technician_id=owner.id, title="t", category="آنتی‌ویروس"))
    db.commit()
    dlg = KeyActivityDialog(db, owner)
    items = [dlg.cmb_category.itemText(i) for i in range(dlg.cmb_category.count())]
    assert items[0] == ""
    assert "شبکه" in items and "آنتی‌ویروس" in items
    assert dlg.cmb_category.isEditable()

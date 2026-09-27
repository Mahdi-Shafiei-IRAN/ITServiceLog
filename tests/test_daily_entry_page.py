"""صفحه‌ی ثبت روزانه‌ی واحد IT: مرز ردیف‌ها و ربطِ هر شمارنده به خدمتش.

کاربر عددِ خدمتِ کناری را اشتباهی بالا برده بود: نام خدمت در یک سرِ ردیف و شمارنده در
سرِ دیگر بود، مرز ردیف‌ها دیده نمی‌شد و کنار هر خدمت یک چک‌باکسِ بی‌کار هم بود.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView

from database.models import Task, DEPT_IT
from ui.daily_entry_page import DailyEntryPage


def _tasks(db):
    root = Task(title="نصب نرم افزار", department=DEPT_IT, position=1)
    db.add(root)
    db.flush()
    subs = [Task(title=t, department=DEPT_IT, parent_task_id=root.id, position=i)
            for i, t in enumerate(["office", "chrome", "firefox"], start=1)]
    db.add_all(subs)
    db.commit()
    return root, subs


def test_it_entry_has_no_dead_checkboxes(qapp, db, owner, dialogs):
    _tasks(db)
    page = DailyEntryPage(db, owner, DEPT_IT)
    page._clear_counts()   # همان مسیری که قبلاً روی همه‌ی ردیف‌ها تیک می‌گذاشت
    for item in page.task_items.values():
        assert not (item.flags() & Qt.ItemIsUserCheckable)
        assert item.data(0, Qt.CheckStateRole) is None


def test_counter_sits_next_to_the_name(qapp, db, owner, dialogs):
    _tasks(db)
    page = DailyEntryPage(db, owner, DEPT_IT)
    header = page.task_tree.header()
    # ستون نام کشسان نیست؛ فضای خالی به ستون آخر (بعد از شمارنده) می‌رود
    assert header.sectionResizeMode(0) == QHeaderView.ResizeToContents
    assert header.sectionResizeMode(2) == QHeaderView.Stretch
    assert page.task_tree.alternatingRowColors()


def test_row_with_a_count_is_marked(qapp, db, owner, dialogs):
    _, subs = _tasks(db)
    page = DailyEntryPage(db, owner, DEPT_IT)
    item = page.task_items[subs[1].id]
    assert not item.font(0).bold()
    page.count_widgets[subs[1].id].setValue(2)
    assert item.font(0).bold()
    assert item.data(0, Qt.BackgroundRole) is not None
    page.count_widgets[subs[1].id].setValue(0)
    assert not item.font(0).bold()
    assert item.data(0, Qt.BackgroundRole) is None


def test_pointing_at_a_counter_selects_its_row(qapp, db, owner, dialogs):
    _, subs = _tasks(db)
    page = DailyEntryPage(db, owner, DEPT_IT)
    page.count_widgets[subs[2].id].activated.emit()
    assert page.task_items[subs[2].id].isSelected()
    page.count_widgets[subs[0].id].activated.emit()
    assert page.task_items[subs[0].id].isSelected()
    assert not page.task_items[subs[2].id].isSelected()


def test_saved_counts_reload_marked(qapp, db, owner, dialogs):
    _, subs = _tasks(db)
    page = DailyEntryPage(db, owner, DEPT_IT)
    page.count_widgets[subs[0].id].setValue(3)
    page.save_record()
    page.load_data()
    assert page.count_widgets[subs[0].id].value() == 3
    assert page.task_items[subs[0].id].font(0).bold()
    assert not page.task_items[subs[1].id].font(0).bold()

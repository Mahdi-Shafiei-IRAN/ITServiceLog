import pytest
from sqlalchemy import text

from database.models import Technician
from ui.main_window import MainWindow
from ui.technicians_page import TechniciansPage

OWNER_TAB = "کارهای شاخص IT"
ADMIN_TAB = "گزارش کارهای شاخص"


@pytest.fixture
def open_window(qapp, dialogs):
    windows = []

    def _open(tech):
        win = MainWindow(tech)
        windows.append(win)
        return win

    yield _open
    for win in windows:
        win.db_session.close()


def _titles(win):
    return [win.tabs.tabText(i) for i in range(win.tabs.count())]


def test_flagged_user_gets_entry_tab_after_daily_entry(db, owner, open_window):
    titles = _titles(open_window(owner))
    assert OWNER_TAB in titles and ADMIN_TAB not in titles
    assert titles.index(OWNER_TAB) == 1   # owner فقط بخش IT دارد: تب ثبت روزانه، سپس این تب


def test_admin_gets_entry_and_report_tabs_without_flag(db, admin, open_window):
    """مدیر (مثلاً مدیر واحد IT) بدون هیچ تیکی هم باید بتواند کارهایش را ثبت کند؛
    پیش‌تر فقط تب گزارشِ فقط‌خواندنی را می‌دید و جایی برای ثبت نداشت."""
    assert not admin.can_log_key_activities
    titles = _titles(open_window(admin))
    assert OWNER_TAB in titles and ADMIN_TAB in titles
    assert titles.index(ADMIN_TAB) == titles.index("گزارشات کلی واحد سایت") + 1
    assert titles.index(OWNER_TAB) < titles.index("گزارش‌های من")


def test_flagged_admin_gets_both_tabs(db, admin, open_window):
    admin.can_log_key_activities = True
    db.commit()
    titles = _titles(open_window(admin))
    assert OWNER_TAB in titles and ADMIN_TAB in titles


def test_plain_technician_gets_neither(db, other, open_window):
    titles = _titles(open_window(other))
    assert OWNER_TAB not in titles and ADMIN_TAB not in titles


def _row_of(page, tech):
    return next(i for i, t in enumerate(page.techs) if t.id == tech.id)


def test_admin_grants_access_to_existing_user(qapp, db, admin, other, dialogs):
    page = TechniciansPage(db, admin)
    assert page.table.horizontalHeaderItem(6).text() == "کارهای شاخص"
    page.table.setCurrentCell(_row_of(page, other), 0)
    assert not page.chk_key_activities.isChecked()
    page.chk_key_activities.setChecked(True)
    page.save_technician()
    db.refresh(other)
    assert other.can_log_key_activities is True
    assert page.table.item(_row_of(page, other), 6).text() == "✓"
    assert not page.chk_key_activities.isChecked()   # clear_form پس از ذخیره
    assert page.editing_id is None


def test_selecting_flagged_user_checks_box(qapp, db, admin, owner, dialogs):
    page = TechniciansPage(db, admin)
    page.table.setCurrentCell(_row_of(page, owner), 0)
    assert page.chk_key_activities.isChecked()
    assert page.chk_key_activities.isEnabled()
    # مدیر همیشه دسترسی دارد و این در جدول هم روشن است
    assert page.table.item(_row_of(page, admin), 6).text() == "✓ (مدیر)"


def test_admin_role_locks_checkbox_on_without_losing_real_flag(qapp, db, admin, other, dialogs):
    page = TechniciansPage(db, admin)
    page.table.setCurrentCell(_row_of(page, admin), 0)
    assert page.chk_key_activities.isChecked() and not page.chk_key_activities.isEnabled()

    # کارشناسِ بدون تیک → اگر نقشش موقتاً مدیر شود تیک قفل می‌شود، و با برگشتن به
    # کارشناس دوباره همان «بدون تیک» واقعی‌اش برمی‌گردد
    page.table.setCurrentCell(_row_of(page, other), 0)
    assert not page.chk_key_activities.isChecked() and page.chk_key_activities.isEnabled()
    page.cmb_role.setCurrentText("Administrator")
    assert page.chk_key_activities.isChecked() and not page.chk_key_activities.isEnabled()
    page.cmb_role.setCurrentText("Technician")
    assert not page.chk_key_activities.isChecked() and page.chk_key_activities.isEnabled()


def test_null_key_activities_flag_hides_owner_tab_and_shows_dash(qapp, db, admin, open_window):
    """ردیفی که نسخه‌ی قدیمی‌تر برنامه نوشته (ستون تازه NULL است، نه False)."""
    legacy = Technician(full_name="کارشناس قدیمی", username="legacyuser",
                        password_hash="x", role="Technician", department="IT",
                        is_active=True)
    db.add(legacy)
    db.commit()
    # روی ستونِ Column(default=False)، نوشتنِ None از طریق ORM باعث اعمال همان
    # پیش‌فرض (False) می‌شود، نه NULL واقعی؛ پس NULL را مستقیماً با SQL خام می‌نویسیم
    # تا رفتار رکوردهای قدیمی (قبل از این ستون) واقعاً شبیه‌سازی شود.
    db.execute(text("UPDATE technicians SET can_log_key_activities = NULL WHERE id = :i"),
              {"i": legacy.id})
    db.commit()
    stored = db.execute(
        text("SELECT can_log_key_activities FROM technicians WHERE id = :i"),
        {"i": legacy.id}).scalar()
    assert stored is None
    db.refresh(legacy)  # شیء ORM را با مقدار واقعیِ NULL هم‌سو می‌کند

    titles = _titles(open_window(legacy))
    assert OWNER_TAB not in titles

    page = TechniciansPage(db, admin)
    row = _row_of(page, legacy)
    assert page.table.item(row, 6).text() == "–"


def test_new_user_with_access(qapp, db, admin, dialogs):
    page = TechniciansPage(db, admin)
    page.txt_name.setText("کاربر جدید")
    page.txt_user.setText("newuser")
    page.txt_pass.setText("pw")
    page.chk_key_activities.setChecked(True)
    page.save_technician()
    created = db.query(Technician).filter_by(username="newuser").one()
    assert created.can_log_key_activities is True

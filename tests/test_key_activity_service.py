from datetime import date, datetime

import pytest

from database.models import (KeyActivity, KeyActivityUpdate, KEY_CATEGORIES_DEFAULT,
                             KEY_STATUS_DONE, KEY_STATUS_IN_PROGRESS, KEY_STATUS_ON_HOLD,
                             KEY_STATUS_CANCELLED, KEY_PRIORITY_NORMAL, KEY_PRIORITY_TOP)
from services import key_activity_service as svc

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def make(title="کار", start=date(2026, 9, 10), end=None, status=KEY_STATUS_IN_PROGRESS, **kw):
    return KeyActivity(title=title, start_date=start, end_date=end, status=status, **kw)


def dataset():
    a1 = make("A1", start=date(2026, 9, 5), end=date(2026, 9, 20), status=KEY_STATUS_DONE,
              category="شبکه", priority=KEY_PRIORITY_TOP, technician_id=1)
    a1.updates.append(KeyActivityUpdate(update_date=date(2026, 9, 20), text="تمام شد"))
    a2 = make("A2", start=date(2026, 8, 1), category="سرور", priority=KEY_PRIORITY_NORMAL,
              technician_id=2)
    a2.updates.append(KeyActivityUpdate(update_date=date(2026, 8, 15), text="شروع"))
    a2.updates.append(KeyActivityUpdate(update_date=date(2026, 9, 12), text="ادامه"))
    a3 = make("A3", start=date(2026, 9, 10), status=KEY_STATUS_ON_HOLD, category=None,
              priority=None, technician_id=2)
    a4 = make("A4", start=date(2026, 8, 1), end=date(2026, 8, 20), status=KEY_STATUS_DONE,
              category="شبکه", priority=KEY_PRIORITY_NORMAL, technician_id=2)
    a5 = make("A5", start=date(2026, 9, 25), category="شبکه", priority=KEY_PRIORITY_NORMAL,
              technician_id=2)
    return [a1, a2, a3, a4, a5]


# ------------------------------------------------------------------ in_period
def test_all_time_includes_everything():
    assert svc.in_period(make(start=date(2020, 1, 1)), None)


def test_open_activity_started_before_period_is_included():
    assert svc.in_period(make(start=date(2026, 8, 1)), SEPT)


def test_activity_started_after_period_is_excluded():
    assert not svc.in_period(make(start=date(2026, 10, 1)), SEPT)


def test_activity_finished_before_period_is_excluded():
    assert not svc.in_period(make(start=date(2026, 8, 1), end=date(2026, 8, 31),
                                  status=KEY_STATUS_DONE), SEPT)


def test_period_edges_are_inclusive():
    assert svc.in_period(make(start=date(2026, 9, 30)), SEPT)
    assert svc.in_period(make(start=date(2026, 8, 1), end=date(2026, 9, 1),
                              status=KEY_STATUS_DONE), SEPT)


def test_open_activity_with_past_manual_end_date_is_still_in_period():
    """تاریخ اتمامِ دستی روی یک کارِ باز نباید آن را از بازه‌های بعدی مخفی کند."""
    act = make(start=date(2026, 8, 1), end=date(2026, 8, 10), status=KEY_STATUS_IN_PROGRESS)
    assert svc.in_period(act, SEPT)


def test_cancelled_activity_ended_in_january_excluded_from_september():
    act = make(start=date(2026, 1, 1), end=date(2026, 1, 15), status=KEY_STATUS_CANCELLED)
    assert not svc.in_period(act, SEPT)


# ------------------------------------------------------------------ updates / summary
def test_updates_in_period_sorted_ascending():
    acts = dataset()
    ups = svc.updates_in_period(acts, SEPT)
    assert [u.text for u in ups] == ["ادامه", "تمام شد"]
    assert len(svc.updates_in_period(acts, None)) == 3


def test_summarize_period():
    s = svc.summarize(dataset(), SEPT)
    assert s["total"] == 4
    assert s["done_in_period"] == 1
    assert s["started_in_period"] == 3
    assert s["in_progress"] == 2
    assert s["updates_in_period"] == 2
    assert s["by_status"] == {KEY_STATUS_DONE: 1, KEY_STATUS_IN_PROGRESS: 2, KEY_STATUS_ON_HOLD: 1}
    assert s["by_category"] == {"شبکه": 2, "سرور": 1, svc.UNKNOWN: 1}
    assert s["by_priority"] == {KEY_PRIORITY_TOP: 1, KEY_PRIORITY_NORMAL: 2, svc.UNKNOWN: 1}


def test_summarize_all_time():
    s = svc.summarize(dataset(), None)
    assert s["total"] == 5
    assert s["done_in_period"] == 2
    assert s["started_in_period"] == 5
    assert s["in_progress"] == 2
    assert s["updates_in_period"] == 3


# ------------------------------------------------------------------ apply_status
def test_apply_done_sets_full_progress_and_end_date():
    act = make(progress=40)
    svc.apply_status(act, KEY_STATUS_DONE, date(2026, 9, 15))
    assert act.status == KEY_STATUS_DONE
    assert act.progress == 100
    assert act.end_date == date(2026, 9, 15)


def test_apply_done_keeps_existing_end_date():
    act = make(end=date(2026, 9, 12), progress=40)
    svc.apply_status(act, KEY_STATUS_DONE, date(2026, 9, 15))
    assert act.end_date == date(2026, 9, 12)


def test_leaving_done_clears_end_date_but_keeps_progress():
    act = make(end=date(2026, 9, 12), status=KEY_STATUS_DONE, progress=100)
    svc.apply_status(act, KEY_STATUS_IN_PROGRESS, date(2026, 9, 15))
    assert act.status == KEY_STATUS_IN_PROGRESS
    assert act.end_date is None
    assert act.progress == 100


def test_non_done_transition_keeps_manual_end_date():
    act = make(end=date(2026, 9, 30), status=KEY_STATUS_IN_PROGRESS)
    svc.apply_status(act, KEY_STATUS_ON_HOLD, date(2026, 9, 15))
    assert act.end_date == date(2026, 9, 30)


def test_apply_cancelled_sets_end_date_and_keeps_progress():
    act = make(progress=40)
    svc.apply_status(act, KEY_STATUS_CANCELLED, date(2026, 9, 15))
    assert act.status == KEY_STATUS_CANCELLED
    assert act.end_date == date(2026, 9, 15)
    assert act.progress == 40


def test_leaving_cancelled_clears_end_date():
    act = make(end=date(2026, 9, 12), status=KEY_STATUS_CANCELLED, progress=40)
    svc.apply_status(act, KEY_STATUS_IN_PROGRESS, date(2026, 9, 15))
    assert act.status == KEY_STATUS_IN_PROGRESS
    assert act.end_date is None
    assert act.progress == 40


def test_done_to_cancelled_keeps_end_date():
    act = make(end=date(2026, 9, 12), status=KEY_STATUS_DONE, progress=100)
    svc.apply_status(act, KEY_STATUS_CANCELLED, date(2026, 9, 20))
    assert act.status == KEY_STATUS_CANCELLED
    assert act.end_date == date(2026, 9, 12)
    assert act.progress == 100


# ------------------------------------------------------------------ add_update
def _saved_activity(db, owner, **kw):
    kw.setdefault("start_date", date(2026, 9, 1))
    kw.setdefault("status", KEY_STATUS_IN_PROGRESS)
    kw.setdefault("progress", 10)
    act = KeyActivity(technician_id=owner.id, technician_name_snapshot=owner.full_name,
                      title="سرور بکاپ", **kw)
    db.add(act)
    db.commit()
    return act


def test_add_update_applies_progress(db, owner):
    act = _saved_activity(db, owner)
    before = act.updated_at
    upd = svc.add_update(db, act, date(2026, 9, 15), "  خرید استوریج  ", progress=40,
                         author=owner.full_name)
    db.commit()
    assert upd.text == "خرید استوریج"
    assert upd.author_name_snapshot == owner.full_name
    assert act.progress == 40
    assert act.status == KEY_STATUS_IN_PROGRESS
    assert act.end_date is None
    assert (upd.progress, upd.status) == (40, KEY_STATUS_IN_PROGRESS)
    assert len(act.updates) == 1
    assert act.updated_at >= before


def test_add_update_done_sets_end_date_and_full_progress(db, owner):
    act = _saved_activity(db, owner)
    upd = svc.add_update(db, act, date(2026, 9, 20), "تحویل شد", progress=80,
                         status=KEY_STATUS_DONE)
    db.commit()
    assert act.status == KEY_STATUS_DONE
    assert act.progress == 100
    assert act.end_date == date(2026, 9, 20)
    assert (upd.progress, upd.status) == (100, KEY_STATUS_DONE)


def test_add_update_same_status_does_not_touch_end_date(db, owner):
    act = _saved_activity(db, owner, status=KEY_STATUS_DONE, progress=100,
                          end_date=date(2026, 9, 5))
    svc.add_update(db, act, date(2026, 9, 20), "یادداشت پس از تحویل", status=KEY_STATUS_DONE)
    db.commit()
    assert act.end_date == date(2026, 9, 5)


def test_add_update_progress_below_100_is_forced_back_to_100_when_done(db, owner):
    """یک به‌روزرسانی نباید بتواند کار انجام‌شده را زیر ۱۰۰٪ نگه دارد."""
    act = _saved_activity(db, owner, status=KEY_STATUS_DONE, progress=100,
                          end_date=date(2026, 9, 5))
    svc.add_update(db, act, date(2026, 9, 20), "یادداشت", progress=80, status=KEY_STATUS_DONE)
    db.commit()
    assert act.progress == 100


def test_add_update_before_start_date_is_rejected(db, owner):
    act = _saved_activity(db, owner, start_date=date(2026, 9, 10))
    with pytest.raises(ValueError):
        svc.add_update(db, act, date(2026, 9, 5), "زودتر از شروع")
    assert act.updates == []


@pytest.mark.parametrize("kwargs", [
    {"text": "   "},
    {"text": "ok", "progress": 101},
    {"text": "ok", "progress": -1},
    {"text": "ok", "status": "نامعتبر"},
])
def test_add_update_rejects_invalid_input(db, owner, kwargs):
    act = _saved_activity(db, owner)
    with pytest.raises(ValueError):
        svc.add_update(db, act, date(2026, 9, 15), **kwargs)
    assert act.updates == []


# ------------------------------------------------------------------ validation
def test_validate_activity_messages():
    assert svc.validate_activity("کار", date(2026, 9, 1), None, 0) == []
    assert svc.validate_activity("  ", date(2026, 9, 1), None, 0) == ["عنوان کار الزامی است."]
    assert svc.validate_activity("کار", None, None, 0) == ["تاریخ شروع الزامی است."]
    assert svc.validate_activity("کار", date(2026, 9, 10), date(2026, 9, 1), 0) == [
        "تاریخ اتمام نمی‌تواند قبل از تاریخ شروع باشد."]
    assert svc.validate_activity("کار", date(2026, 9, 1), None, 120) == [
        "درصد پیشرفت باید بین ۰ تا ۱۰۰ باشد."]


# ------------------------------------------------------------------ suggestions
def test_category_suggestions_defaults_then_used(db, owner):
    for cat in ["ذخیره‌سازی", "شبکه", "  ", None, "آنتی‌ویروس", "ذخیره‌سازی"]:
        db.add(KeyActivity(technician_id=owner.id, title="t", category=cat))
    db.commit()
    assert svc.category_suggestions(db) == KEY_CATEGORIES_DEFAULT + ["آنتی‌ویروس", "ذخیره‌سازی"]


# ------------------------------------------------------------------ helpers
def test_last_update_date_and_timeline():
    act = make()
    assert svc.last_update_date(act) is None
    for d in (date(2026, 9, 1), date(2026, 9, 15), date(2026, 9, 10)):
        act.updates.append(KeyActivityUpdate(update_date=d, text=str(d)))
    assert svc.last_update_date(act) == date(2026, 9, 15)
    assert [u.update_date for u in svc.timeline(act)] == [
        date(2026, 9, 15), date(2026, 9, 10), date(2026, 9, 1)]


def test_filter_activities():
    acts = dataset()
    titles = lambda xs: [a.title for a in xs]
    assert titles(svc.filter_activities(acts)) == ["A1", "A2", "A3", "A4", "A5"]
    assert titles(svc.filter_activities(acts, rng=SEPT)) == ["A1", "A2", "A3", "A5"]
    assert titles(svc.filter_activities(acts, status=KEY_STATUS_DONE)) == ["A1", "A4"]
    assert titles(svc.filter_activities(acts, category="شبکه")) == ["A1", "A4", "A5"]
    assert titles(svc.filter_activities(acts, priority=KEY_PRIORITY_TOP)) == ["A1"]
    assert titles(svc.filter_activities(acts, owner_id=1)) == ["A1"]
    assert titles(svc.filter_activities(acts, words=["ادامه"])) == ["A2"]   # متن به‌روزرسانی
    assert titles(svc.filter_activities(acts, words=["a1"])) == ["A1"]      # بی‌حساس به حروف


def test_sort_activities_open_first_then_recent():
    a = make("a", status=KEY_STATUS_DONE, updated_at=datetime(2026, 9, 20))
    b = make("b", updated_at=datetime(2026, 9, 1))
    c = make("c", updated_at=datetime(2026, 9, 15))
    d = make("d", status=KEY_STATUS_CANCELLED, updated_at=datetime(2026, 9, 25))
    assert [x.title for x in svc.sort_activities([a, b, c, d])] == ["c", "b", "d", "a"]

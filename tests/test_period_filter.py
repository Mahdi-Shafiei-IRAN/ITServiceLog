from datetime import date

from ui.period_filter import PeriodFilter, period_range, week_start

TODAY = date(2026, 9, 26)   # شنبه


def test_week_starts_on_saturday():
    assert week_start(date(2026, 9, 26)) == date(2026, 9, 26)   # شنبه
    assert week_start(date(2026, 10, 2)) == date(2026, 9, 26)   # جمعه
    assert week_start(date(2026, 9, 27)) == date(2026, 9, 26)   # یکشنبه


def test_period_ranges():
    assert period_range("all", TODAY) is None
    assert period_range("today", TODAY) == (TODAY, TODAY)
    assert period_range("yesterday", TODAY) == (date(2026, 9, 25), date(2026, 9, 25))
    assert period_range("last7", TODAY) == (date(2026, 9, 20), TODAY)
    assert period_range("last30", TODAY) == (date(2026, 8, 28), TODAY)
    assert period_range("this_week", TODAY) == (date(2026, 9, 26), TODAY)
    assert period_range("last_week", TODAY) == (date(2026, 9, 19), date(2026, 9, 25))
    # ماه‌ها شمسی‌اند: ۴ مهر ۱۴۰۵ → از ۱ مهر؛ ماه گذشته = کل شهریور
    assert period_range("this_month", TODAY) == (date(2026, 9, 23), TODAY)
    assert period_range("last_month", TODAY) == (date(2026, 8, 23), date(2026, 9, 22))


def test_custom_range_is_ordered():
    a, b = date(2026, 9, 10), date(2026, 9, 1)
    assert period_range("custom", TODAY, a, b) == (b, a)
    assert period_range("custom", TODAY, b, a) == (b, a)


def test_preset_shows_the_range_it_applies(qapp):
    """پیش‌تر در «این ماه» کادرهای از/تا تاریخِ ثابتِ «۳۰ روز پیش» را نشان می‌دادند،
    در حالی که فیلتر از اول ماه اعمال می‌شد."""
    w = PeriodFilter(default="this_month")
    rng = w.date_range()
    assert (w.date_from.date().toPython(), w.date_to.date().toPython()) == rng
    w.set_key("last_week")
    assert (w.date_from.date().toPython(), w.date_to.date().toPython()) == w.date_range()


def test_all_time_hides_dates(qapp):
    w = PeriodFilter(default="all")
    assert w.date_from.isHidden() and w.date_to.isHidden()
    w.set_key("custom")
    assert not w.date_from.isHidden() and not w.date_to.isHidden()


def test_switching_to_custom_starts_from_the_shown_range(qapp):
    w = PeriodFilter(default="last_month")
    shown = w.date_range()
    w.set_key("custom")
    assert w.date_range() == shown


def test_widget_default_and_custom_toggle(qapp):
    w = PeriodFilter(default="this_month")
    assert w.key() == "this_month"
    assert not w.date_from.isEnabled() and not w.date_to.isEnabled()
    fired = []
    w.changed.connect(lambda: fired.append(1))
    w.set_key("custom")
    assert w.date_from.isEnabled() and w.date_to.isEnabled()
    assert fired
    w.set_key("all")
    assert w.date_range() is None

import os

import pytest

from ui.theme import LIGHT, DARK, build_stylesheet, _chevron_icons


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_both_palettes_build_complete_stylesheets(qapp, palette):
    # کلید جاافتاده در پالت = KeyError در استارتاپ برنامه
    assert set(LIGHT) == set(DARK)
    icons = _chevron_icons(palette)
    assert icons is not None
    for path in icons.values():
        assert os.path.exists(path)
    qss = build_stylesheet(palette, icons)
    assert "%(" not in qss
    assert icons["chevron_down"] in qss
    assert "QDateEdit" in qss and "QProgressBar" in qss


def test_stylesheet_without_icons_still_builds():
    # اگر ساخت فایل فلش‌ها شکست بخورد، برنامه باید بدون فلش (نه با url خراب) اجرا شود
    qss = build_stylesheet(LIGHT)
    assert "chevron" not in qss and "url(" not in qss

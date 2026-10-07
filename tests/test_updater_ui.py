from PySide6.QtWidgets import QWidget

from ui import updater


def test_later_is_not_asked_again_this_session(qapp, monkeypatch):
    rel = {"version": "9.9.9", "notes": "", "file_name": "x.exe", "size": 1, "sha256": "", "id": 1}
    monkeypatch.setattr(updater.update_service, "newer_release", lambda engine: rel)
    asked = []
    monkeypatch.setattr(updater.UpdateChecker, "_ask", lambda self, r: asked.append(r) or False)
    checker = updater.UpdateChecker(QWidget())
    checker.check()
    checker.check()
    assert len(asked) == 1 and not checker._busy


def test_server_down_is_silent(qapp, monkeypatch):
    def boom(engine):
        raise OSError("down")
    monkeypatch.setattr(updater.update_service, "newer_release", boom)
    updater.UpdateChecker(QWidget()).check()   # بدون خطا و بدون پیام

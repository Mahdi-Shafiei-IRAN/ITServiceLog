

def test_mouse_wheel_does_not_change_date(qapp):
    from PySide6.QtCore import QDate, QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication
    from ui.date_edit import JalaliDateEdit
    w = JalaliDateEdit()
    w.setDate(QDate(2026, 10, 7))
    w.show()
    w.setFocus()
    w.setCurrentSection(w.Section.YearSection)
    for delta in (120, -120, -120 * 20):
        ev = QWheelEvent(QPointF(5, 5), QPointF(w.mapToGlobal(QPoint(5, 5))), QPoint(0, 0),
                         QPoint(0, delta), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        QApplication.sendEvent(w, ev)
    assert w.date() == QDate(2026, 10, 7)

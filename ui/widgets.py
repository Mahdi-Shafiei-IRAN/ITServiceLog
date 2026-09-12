"""ویجت‌های کمکی مشترک."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QToolButton
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt, Signal


class CountStepper(QWidget):
    """شمارنده‌ی تعداد با دو دکمه‌ی فلش بالا/پایین و یک فیلد عددی.

    جایگزین QSpinBox است تا:
      • با اسکرول ماوس تغییر نکند (فقط کلیک روی فلش‌ها یا تایپ).
      • ظاهر تمیز و هماهنگ با تم داشته باشد.
    سازگار با API لازم: value() / setValue() / setRange().
    """

    valueChanged = Signal(int)

    def __init__(self, minimum=0, maximum=999, parent=None):
        super().__init__(parent)
        self._min, self._max = minimum, maximum

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.edit = QLineEdit("0")
        self.edit.setObjectName("StepperEdit")
        self.edit.setValidator(QIntValidator(minimum, maximum, self))
        self.edit.setAlignment(Qt.AlignCenter)
        self.edit.textChanged.connect(lambda *_: self.valueChanged.emit(self.value()))

        buttons = QVBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(0)
        self.btn_up = QToolButton()
        self.btn_up.setObjectName("StepUp")
        self.btn_up.setText("▲")
        self.btn_down = QToolButton()
        self.btn_down.setObjectName("StepDown")
        self.btn_down.setText("▼")
        for b in (self.btn_up, self.btn_down):
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setAutoRepeat(True)  # نگه‌داشتن دکمه، شمارش را ادامه می‌دهد
        self.btn_up.clicked.connect(lambda: self.setValue(self.value() + 1))
        self.btn_down.clicked.connect(lambda: self.setValue(self.value() - 1))
        buttons.addWidget(self.btn_up)
        buttons.addWidget(self.btn_down)

        layout.addWidget(self.edit, 1)
        layout.addLayout(buttons)

    def value(self) -> int:
        try:
            v = int(self.edit.text() or 0)
        except ValueError:
            return self._min
        return max(self._min, min(self._max, v))

    def setValue(self, v):
        v = max(self._min, min(self._max, int(v)))
        if str(v) != self.edit.text():
            self.edit.setText(str(v))

    def setRange(self, lo, hi):
        self._min, self._max = lo, hi
        self.edit.setValidator(QIntValidator(lo, hi, self))

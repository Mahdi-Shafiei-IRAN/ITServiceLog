"""ویجت‌های کمکی مشترک."""
from PySide6.QtWidgets import QSpinBox
from PySide6.QtCore import Qt


class NoWheelSpinBox(QSpinBox):
    """اسپین‌باکسی که با چرخاندن اسکرول ماوس تغییر نمی‌کند.

    فقط با کلیک روی دکمه‌های بالا/پایین یا تایپ عدد تغییر می‌کند تا هنگام
    اسکرول صفحه، تعدادها به‌اشتباه کم/زیاد نشوند.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # با StrongFocus، چرخ ماوس تا وقتی فوکوس روی ویجت نباشد اثری ندارد
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        # رویداد چرخ را نادیده می‌گیریم تا به اسکرول صفحه منتقل شود
        event.ignore()

"""ظرفِ ساده برای گروه‌بندی چند صفحه‌ی گزارش زیرِ یک تب، با تب‌های داخلی.

هنگام باز شدنِ تبِ بیرونی (load_data) یا جابه‌جایی بین تب‌های داخلی، همان صفحه‌ی
نمایان تازه‌سازی می‌شود (بقیه هنگام انتخاب تازه می‌شوند تا سبک بماند).
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget


def _refresh(widget):
    for method in ("load_data", "load_records", "load_tasks",
                   "load_technicians", "refresh_dashboard"):
        if hasattr(widget, method):
            getattr(widget, method)()
            return


class ReportTabs(QWidget):
    def __init__(self, children, parent=None):
        """children: لیستی از (عنوان, ویجت)."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        for title, widget in children:
            self.tabs.addTab(widget, title)
        self.tabs.currentChanged.connect(self._on_inner_changed)
        layout.addWidget(self.tabs)

    def _on_inner_changed(self, index):
        w = self.tabs.widget(index)
        if w is not None:
            _refresh(w)

    def load_data(self):
        # صفحه‌ی نمایان را تازه کن (بقیه هنگام انتخاب تازه می‌شوند)
        w = self.tabs.currentWidget()
        if w is not None:
            _refresh(w)

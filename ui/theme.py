"""
سیستم تم مرکزی برنامه (روشن / تیره).

همه‌ی رنگ‌ها از یک پالت خوانده می‌شوند تا ظاهر برنامه یکدست بماند و
با یک کلید بین حالت روشن و تیره جابه‌جا شود. انتخاب کاربر با QSettings
ذخیره می‌شود و در اجرای بعدی به‌خاطر سپرده می‌شود.
"""

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import QObject, Signal, QSettings, Qt


# ----------------------------------------------------------------------
#  پالت رنگ‌ها
# ----------------------------------------------------------------------
LIGHT = {
    "bg":            "#F1F5F9",
    "surface":       "#FFFFFF",
    "surface_alt":   "#F8FAFC",
    "surface_muted": "#F1F5F9",
    "border":        "#E2E8F0",
    "border_strong": "#CBD5E1",
    "text":          "#1E293B",
    "text_muted":    "#64748B",
    "primary":       "#2563EB",
    "primary_hover": "#1D4ED8",
    "primary_press": "#1E40AF",
    "on_primary":    "#FFFFFF",
    "success":       "#10B981",
    "success_hover": "#059669",
    "danger":        "#EF4444",
    "danger_hover":  "#DC2626",
    "input_bg":      "#FFFFFF",
    "selection_bg":  "#DBEAFE",
    "selection_text": "#1E40AF",
}

DARK = {
    "bg":            "#0F172A",
    "surface":       "#1E293B",
    "surface_alt":   "#243449",
    "surface_muted": "#334155",
    "border":        "#334155",
    "border_strong": "#475569",
    "text":          "#E2E8F0",
    "text_muted":    "#94A3B8",
    "primary":       "#3B82F6",
    "primary_hover": "#60A5FA",
    "primary_press": "#2563EB",
    "on_primary":    "#FFFFFF",
    "success":       "#10B981",
    "success_hover": "#34D399",
    "danger":        "#EF4444",
    "danger_hover":  "#F87171",
    "input_bg":      "#16233B",
    "selection_bg":  "#1E3A8A",
    "selection_text": "#DBEAFE",
}


# ----------------------------------------------------------------------
#  استایل‌شیت اصلی (بر اساس پالت جاری ساخته می‌شود)
# ----------------------------------------------------------------------
_QSS_TEMPLATE = """
* {
    font-family: 'Segoe UI', 'Tahoma', 'Vazirmatn', 'Iran Sans', sans-serif;
    font-size: 13px;
    outline: none;
}

QWidget {
    background-color: %(bg)s;
    color: %(text)s;
}

QMainWindow, QDialog {
    background-color: %(bg)s;
}

QToolTip {
    background-color: %(surface)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 6px 8px;
}

/* ---------- کارت‌ها و گروپ‌باکس‌ها ---------- */
QGroupBox {
    background-color: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
    margin-top: 16px;
    padding: 16px 14px 14px 14px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top right;
    right: 14px;
    padding: 2px 8px;
    color: %(text_muted)s;
}

QFrame#Card {
    background-color: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
}

/* ---------- برچسب‌ها ---------- */
QLabel { background: transparent; color: %(text)s; }
QLabel#PageTitle    { font-size: 22px; font-weight: bold; color: %(text)s; }
QLabel#SectionTitle { font-size: 15px; font-weight: bold; color: %(text)s; }
QLabel#Muted        { color: %(text_muted)s; font-size: 12px; }

/* ---------- دکمه‌ها ---------- */
QPushButton {
    background-color: %(primary)s;
    color: %(on_primary)s;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover   { background-color: %(primary_hover)s; }
QPushButton:pressed { background-color: %(primary_press)s; }
QPushButton:disabled { background-color: %(border_strong)s; color: %(text_muted)s; }

QPushButton[variant="success"] { background-color: %(success)s; }
QPushButton[variant="success"]:hover { background-color: %(success_hover)s; }

QPushButton[variant="danger"] { background-color: %(danger)s; }
QPushButton[variant="danger"]:hover { background-color: %(danger_hover)s; }

QPushButton[variant="ghost"] {
    background-color: transparent;
    color: %(text)s;
    border: 1px solid %(border_strong)s;
}
QPushButton[variant="ghost"]:hover { background-color: %(surface_alt)s; }

QPushButton#ThemeToggle {
    background-color: %(surface_alt)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 0;
    font-size: 16px;
    font-weight: normal;
}
QPushButton#ThemeToggle:hover { background-color: %(surface_muted)s; }

/* ---------- ورودی‌ها ---------- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: %(input_bg)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: %(primary)s;
    selection-color: %(on_primary)s;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid %(primary)s;
}
QLineEdit:hover, QComboBox:hover { border: 1px solid %(border_strong)s; }
QLineEdit::placeholder { color: %(text_muted)s; }

QComboBox::drop-down { border: none; width: 22px; }

/* ---------- شمارنده‌ی تعداد (CountStepper) ---------- */
QLineEdit#StepperEdit {
    border: 1px solid %(border)s;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    min-height: 34px;
    font-size: 16px;
    font-weight: bold;
    padding: 0 6px;
}
QLineEdit#StepperEdit:focus { border: 1px solid %(primary)s; }
QToolButton#StepUp, QToolButton#StepDown {
    background-color: %(surface_muted)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    width: 30px;
    min-height: 17px;
    max-height: 17px;
    font-size: 11px;
}
QToolButton#StepUp {
    border-top-left-radius: 8px;
    border-bottom: none;
}
QToolButton#StepDown {
    border-bottom-left-radius: 8px;
}
QToolButton#StepUp:hover, QToolButton#StepDown:hover {
    background-color: %(primary)s;
    color: %(on_primary)s;
}
QToolButton#StepUp:pressed, QToolButton#StepDown:pressed {
    background-color: %(primary_press)s;
    color: %(on_primary)s;
}

/* ---------- اسپین‌باکس (شمارنده‌ی تعداد) ---------- */
QSpinBox, QDoubleSpinBox {
    background-color: %(input_bg)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding-right: 12px;      /* جای عدد در سمت راست */
    min-height: 34px;
    font-size: 16px;
    font-weight: bold;
}
QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid %(primary)s; }
QSpinBox:hover, QDoubleSpinBox:hover { border: 1px solid %(border_strong)s; }

/* دکمه‌های بالا/پایین سمت چپ، بزرگ و کاملاً کلیک‌پذیر */
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top left;
    width: 30px;
    height: 16px;
    border-right: 1px solid %(border)s;
    border-bottom: 1px solid %(border)s;
    border-top-left-radius: 8px;
    background-color: %(surface_muted)s;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom left;
    width: 30px;
    height: 16px;
    border-right: 1px solid %(border)s;
    border-bottom-left-radius: 8px;
    background-color: %(surface_muted)s;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: %(primary)s;
}
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed,
QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: %(primary_press)s;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 0; height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-bottom: 8px solid %(text_muted)s;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 0; height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 8px solid %(text_muted)s;
}
QComboBox QAbstractItemView {
    background-color: %(surface)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: %(primary)s;
    selection-color: %(on_primary)s;
    outline: none;
}

/* ---------- تب‌ها ---------- */
QTabWidget::pane {
    border: 1px solid %(border)s;
    border-radius: 12px;
    top: -1px;
    background-color: %(bg)s;
}
QTabBar::tab {
    background: transparent;
    color: %(text_muted)s;
    padding: 10px 20px;
    margin: 4px 2px 0 2px;
    border: none;
    border-radius: 8px;
    font-weight: bold;
}
QTabBar::tab:hover    { color: %(text)s; background-color: %(surface_alt)s; }
QTabBar::tab:selected { color: %(primary)s; background-color: %(surface)s; }

/* ---------- جدول‌ها ---------- */
QTableWidget, QTableView {
    background-color: %(surface)s;
    alternate-background-color: %(surface_alt)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
    gridline-color: %(border)s;
    selection-background-color: %(selection_bg)s;
    selection-color: %(selection_text)s;
}
QTableWidget::item, QTableView::item { padding: 6px; }
QHeaderView::section {
    background-color: %(surface_muted)s;
    color: %(text_muted)s;
    font-weight: bold;
    padding: 8px;
    border: none;
    border-bottom: 1px solid %(border)s;
}
QTableCornerButton::section { background-color: %(surface_muted)s; border: none; }

/* ---------- درخت‌ها ---------- */
QTreeWidget, QTreeView {
    background-color: %(surface)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
    padding: 6px;
}
QTreeView::item { padding: 5px; border-radius: 6px; }
QTreeView::item:hover    { background-color: %(surface_alt)s; }
QTreeView::item:selected { background-color: %(selection_bg)s; color: %(selection_text)s; }

/* ---------- اسکرول‌بارها ---------- */
QScrollBar:vertical { background: transparent; width: 12px; margin: 4px; }
QScrollBar::handle:vertical {
    background: %(border_strong)s; border-radius: 5px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: %(text_muted)s; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 4px; }
QScrollBar::handle:horizontal {
    background: %(border_strong)s; border-radius: 5px; min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: %(text_muted)s; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---------- منوها و پیام‌ها ---------- */
QMenu {
    background-color: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item { padding: 6px 20px; border-radius: 6px; }
QMenu::item:selected { background-color: %(primary)s; color: %(on_primary)s; }
QMessageBox { background-color: %(surface)s; }
"""


def build_stylesheet(palette: dict) -> str:
    """استایل‌شیت کامل را از روی پالت داده‌شده می‌سازد."""
    return _QSS_TEMPLATE % palette


# ----------------------------------------------------------------------
#  مدیر تم (سینگلتون)
# ----------------------------------------------------------------------
class _ThemeManager(QObject):
    """نگه‌دارنده‌ی وضعیت تم؛ با تغییر تم سیگنال changed منتشر می‌شود."""

    changed = Signal(str)  # نام تم جدید: "light" یا "dark"

    def __init__(self):
        super().__init__()
        self._settings = QSettings("ITServiceLog", "ITServiceLog")
        name = self._settings.value("theme", "light")
        self._name = name if name in ("light", "dark") else "light"

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_dark(self) -> bool:
        return self._name == "dark"

    @property
    def palette(self) -> dict:
        return DARK if self.is_dark else LIGHT

    def apply(self):
        """استایل‌شیت تم جاری را روی کل برنامه اعمال می‌کند."""
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(self.palette))

    def set_theme(self, name: str):
        if name not in ("light", "dark") or name == self._name:
            return
        self._name = name
        self._settings.setValue("theme", name)
        self.apply()
        self.changed.emit(name)

    def toggle(self):
        self.set_theme("light" if self.is_dark else "dark")


# نمونه‌ی سراسری که همه‌ی ماژول‌ها از آن استفاده می‌کنند
theme = _ThemeManager()


def set_variant(button: QPushButton, variant: str):
    """رنگ معنایی یک دکمه را تعیین می‌کند (success / danger / ghost)."""
    button.setProperty("variant", variant)


def make_theme_toggle(size: int = 34) -> QPushButton:
    """دکمه‌ی کوچک تغییر تم روشن/تیره را می‌سازد."""
    btn = QPushButton()
    btn.setObjectName("ThemeToggle")
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedSize(size, size)

    def refresh_icon():
        btn.setText("☀" if theme.is_dark else "🌙")
        btn.setToolTip("تغییر به حالت روشن" if theme.is_dark else "تغییر به حالت تیره")

    def on_click():
        theme.toggle()
        refresh_icon()

    btn.clicked.connect(on_click)
    refresh_icon()
    return btn

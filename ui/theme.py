"""
سیستم تم مرکزی برنامه (روشن / تیره).

همه‌ی رنگ‌ها از یک پالت خوانده می‌شوند تا ظاهر برنامه یکدست بماند و
با یک کلید بین حالت روشن و تیره جابه‌جا شود. انتخاب کاربر با QSettings
ذخیره می‌شود و در اجرای بعدی به‌خاطر سپرده می‌شود.
"""

import os
import tempfile

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
    "warning":       "#D97706",
    # نوار پیشرفت: رنگ روشنِ نوار تا عدد تیره‌ی روی آن خوانا بماند
    "progress_chunk": "#93C5FD",
    "progress_done":  "#6EE7B7",
    # برچسب‌های رنگیِ وضعیت/اهمیت (پس‌زمینه‌ی ملایم + متن پررنگ)
    "chip_primary_bg": "#DBEAFE", "chip_primary_fg": "#1D4ED8",
    "chip_success_bg": "#D1FAE5", "chip_success_fg": "#047857",
    "chip_warning_bg": "#FEF3C7", "chip_warning_fg": "#B45309",
    "chip_danger_bg":  "#FEE2E2", "chip_danger_fg":  "#B91C1C",
    "chip_muted_bg":   "#F1F5F9", "chip_muted_fg":   "#475569",
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
    "warning":       "#F59E0B",
    "progress_chunk": "#1D4ED8",
    "progress_done":  "#047857",
    "chip_primary_bg": "#1E3A8A", "chip_primary_fg": "#93C5FD",
    "chip_success_bg": "#064E3B", "chip_success_fg": "#6EE7B7",
    "chip_warning_bg": "#78350F", "chip_warning_fg": "#FCD34D",
    "chip_danger_bg":  "#7F1D1D", "chip_danger_fg":  "#FCA5A5",
    "chip_muted_bg":   "#334155", "chip_muted_fg":   "#CBD5E1",
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

QComboBox::drop-down { border: none; width: 26px; }

/* ---------- تاریخ (همه‌ی تاریخ‌های برنامه تقویم کشویی دارند) ---------- */
QDateEdit, QDateTimeEdit, QTimeEdit {
    background-color: %(input_bg)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
    selection-background-color: %(primary)s;
    selection-color: %(on_primary)s;
}
QDateEdit:hover, QDateTimeEdit:hover, QTimeEdit:hover { border: 1px solid %(border_strong)s; }
QDateEdit:focus, QDateTimeEdit:focus, QTimeEdit:focus { border: 1px solid %(primary)s; }
QDateEdit:disabled, QDateTimeEdit:disabled, QTimeEdit:disabled {
    background-color: %(surface_alt)s;
    color: %(text_muted)s;
}
QDateEdit::drop-down, QDateTimeEdit::drop-down { border: none; width: 26px; }

/* تقویمِ کشویی */
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: %(surface_muted)s;
    border: none;
}
QCalendarWidget QToolButton {
    color: %(text)s;
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
}
QCalendarWidget QToolButton:hover { background-color: %(surface)s; }
QCalendarWidget QToolButton::menu-indicator { image: none; width: 0; }
QCalendarWidget QSpinBox {
    font-size: 13px;
    min-height: 0;
    padding: 2px 4px;
}
QCalendarWidget QAbstractItemView:enabled {
    background-color: %(surface)s;
    color: %(text)s;
    selection-background-color: %(primary)s;
    selection-color: %(on_primary)s;
    outline: none;
}
QCalendarWidget QAbstractItemView:disabled { color: %(text_muted)s; }

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
/* فلش‌های بالا/پایین از فایل تصویر ساخته می‌شوند (_ICON_QSS پایین همین فایل)؛
   ترفندِ «مثلث با border» مثل CSS در Qt کار نمی‌کند و مربع توپر می‌کشد. */
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

/* ---------- نوار پیشرفت ---------- */
QProgressBar {
    background-color: %(surface_muted)s;
    border: none;
    border-radius: 7px;
    color: %(text)s;
    text-align: center;
    font-size: 11px;
    font-weight: bold;
    min-height: 14px;
    max-height: 14px;
}
QProgressBar::chunk { background-color: %(progress_chunk)s; border-radius: 7px; }
QProgressBar[state="done"]::chunk { background-color: %(progress_done)s; }
QProgressBar#DetailProgress {
    min-height: 20px;
    max-height: 20px;
    border-radius: 10px;
    font-size: 12px;
}
QProgressBar#DetailProgress::chunk { border-radius: 10px; }

/* ---------- ظرف‌های بی‌رنگ داخل کارت‌ها و سلول‌های جدول ---------- */
QWidget#Transparent { background: transparent; }
QScrollArea#Transparent { background: transparent; border: none; }

QFrame#SubCard {
    background-color: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
}
QLabel#FieldLabel { color: %(text_muted)s; font-size: 12px; font-weight: bold; }

/* خط زمانیِ به‌روزرسانی‌ها */
QTextBrowser#Timeline {
    background-color: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 6px;
}

/* برچسب‌های رنگیِ وضعیت و اهمیت */
QLabel#Chip { border-radius: 10px; padding: 3px 12px; font-size: 12px; font-weight: bold; }
QLabel#Chip[tone="primary"] { background-color: %(chip_primary_bg)s; color: %(chip_primary_fg)s; }
QLabel#Chip[tone="success"] { background-color: %(chip_success_bg)s; color: %(chip_success_fg)s; }
QLabel#Chip[tone="warning"] { background-color: %(chip_warning_bg)s; color: %(chip_warning_fg)s; }
QLabel#Chip[tone="danger"]  { background-color: %(chip_danger_bg)s;  color: %(chip_danger_fg)s; }
QLabel#Chip[tone="muted"]   { background-color: %(chip_muted_bg)s;   color: %(chip_muted_fg)s; }

/* عددهای کارت‌های خلاصه */
QLabel#StatValue { font-size: 26px; font-weight: bold; color: %(text)s; }
QLabel#StatValue[tone="primary"] { color: %(chip_primary_fg)s; }
QLabel#StatValue[tone="success"] { color: %(chip_success_fg)s; }
QLabel#StatValue[tone="warning"] { color: %(chip_warning_fg)s; }

/* راهنمای «هنوز چیزی ثبت نشده» به‌جای جدول خالی */
QLabel#EmptyState {
    background-color: %(surface)s;
    color: %(text_muted)s;
    border: 1px dashed %(border_strong)s;
    border-radius: 12px;
    padding: 32px;
    font-size: 14px;
}
"""

# فلش‌ها فقط وقتی اضافه می‌شوند که فایل‌های تصویرشان ساخته شده باشد
_ICON_QSS = """
QComboBox::down-arrow, QDateEdit::down-arrow, QDateTimeEdit::down-arrow {
    image: url("%(chevron_down)s");
    width: 10px;
    height: 10px;
}
QComboBox::down-arrow:disabled, QDateEdit::down-arrow:disabled,
QDateTimeEdit::down-arrow:disabled {
    image: url("%(chevron_down_faint)s");
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("%(chevron_up)s");
    width: 10px;
    height: 10px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("%(chevron_down)s");
    width: 10px;
    height: 10px;
}
"""


def _chevron_icons(palette: dict):
    """فلش‌های کوچکِ کشویی/تاریخ/اسپین‌باکس را به رنگ تم (PNG) می‌سازد.

    استایل‌شیت Qt فلش را فقط از فایل تصویر می‌کشد؛ پس یک‌بار در پوشه‌ی موقت
    ساخته می‌شوند (نام فایل رنگ را دارد، پس روشن/تیره با هم تداخل ندارند).
    اگر ساخت ممکن نشد None برمی‌گرداند و برنامه بدون فلش ادامه می‌دهد.
    """
    from PySide6.QtGui import QImage, QPainter, QPen, QColor
    from PySide6.QtCore import QPointF

    shapes = {
        "chevron_down": ([(8, 12), (16, 20), (24, 12)], palette["text_muted"]),
        "chevron_down_faint": ([(8, 12), (16, 20), (24, 12)], palette["border_strong"]),
        "chevron_up": ([(8, 20), (16, 12), (24, 20)], palette["text_muted"]),
    }
    try:
        folder = os.path.join(tempfile.gettempdir(), "ITServiceLog-theme")
        os.makedirs(folder, exist_ok=True)
        paths = {}
        for key, (points, color) in shapes.items():
            path = os.path.join(folder, f"{key}-{color.lstrip('#').lower()}.png")
            if not os.path.exists(path):
                img = QImage(32, 32, QImage.Format_ARGB32)
                img.fill(Qt.transparent)
                painter = QPainter(img)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setPen(QPen(QColor(color), 3.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.drawPolyline([QPointF(x, y) for x, y in points])
                painter.end()
                # اول در فایل موقت، بعد جابه‌جایی: دو نسخه‌ی هم‌زمانِ برنامه فایل نیمه‌کاره نبینند
                tmp_path = f"{path}.{os.getpid()}.tmp"
                if not img.save(tmp_path, "PNG"):
                    return None
                os.replace(tmp_path, path)
            paths[key] = path.replace("\\", "/")
        return paths
    except Exception:
        return None


def build_stylesheet(palette: dict, icons: dict = None) -> str:
    """استایل‌شیت کامل را از روی پالت داده‌شده می‌سازد."""
    qss = _QSS_TEMPLATE % palette
    if icons:
        qss += _ICON_QSS % icons
    return qss


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
            app.setStyleSheet(build_stylesheet(self.palette, _chevron_icons(self.palette)))

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


def set_tone(widget, tone: str):
    """رنگ معنایی یک برچسب/نوار (primary / success / warning / danger / muted).

    تغییرِ property بعد از نمایش ویجت بدون polish دوباره اعمال نمی‌شود.
    """
    if widget.property("tone") == tone:
        return
    widget.setProperty("tone", tone)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def tone_color(tone: str) -> str:
    """رنگ متنِ یک tone در تم جاری (برای سلول‌های جدول که QSS ندارند)."""
    return theme.palette.get(f"chip_{tone}_fg", theme.palette["text"])


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

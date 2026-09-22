"""واحد سایت — دو تب دقیقاً مطابق فایل «گزارش مدیریت».

  • تب ۱: «گزارش روزانه»  (نام بستر، نوع فعالیت، شرح کار، وضعیت، توضیحات)
  • تب ۲: «پایش شبکه‌ها» (نام بستر، دنبال‌کننده، بازدید، تعامل، پست، استوری،
                           رشد، وضعیت صفحه، توضیحات)

هر تب یک «برگه‌ی روزانه»ی جدولی است: تاریخ را انتخاب می‌کنید، ردیف‌های همان روز
بارگذاری و قابل ویرایش می‌شوند و ذخیره، همان برگه را جایگزین می‌کند (رکورد تکراری
ساخته نمی‌شود). فیلدهای کشویی با مقادیرِ ثابتِ تعریف‌شده در مدل پر می‌شوند.
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QMessageBox, QDateEdit, QTableWidget,
                               QComboBox, QHeaderView, QAbstractItemView, QTabWidget)
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session

from database.models import (SiteDailyActivity, SiteNetworkStat,
                             SITE_PLATFORMS, SITE_ACTIVITY_TYPES,
                             SITE_STATUSES, SITE_PAGE_STATUSES)

# ---- تعریف ستون‌های هر شیت (کلید = نام ستون در مدل) -----------------------
#   kind: combo | text | int
DAILY_COLUMNS = [
    {"key": "platform", "label": "نام بستر", "kind": "combo",
     "options": SITE_PLATFORMS, "width": 130},
    {"key": "activity_type", "label": "نوع فعالیت", "kind": "combo",
     "options": SITE_ACTIVITY_TYPES, "width": 150},
    {"key": "description", "label": "شرح کار انجام‌شده", "kind": "text",
     "stretch": True, "placeholder": "شرح کار انجام‌شده..."},
    {"key": "status", "label": "وضعیت", "kind": "combo",
     "options": SITE_STATUSES, "width": 150},
    {"key": "note", "label": "توضیحات", "kind": "text",
     "stretch": True, "placeholder": "توضیحات (اختیاری)..."},
]

NETWORK_COLUMNS = [
    {"key": "platform", "label": "نام بستر", "kind": "combo",
     "options": SITE_PLATFORMS, "width": 130},
    {"key": "followers", "label": "دنبال‌کننده/عضو", "kind": "int", "width": 120},
    {"key": "impressions", "label": "بازدید", "kind": "int", "width": 100},
    {"key": "engagement", "label": "تعامل", "kind": "int", "width": 95},
    {"key": "posts", "label": "پست", "kind": "int", "width": 75},
    {"key": "stories", "label": "استوری", "kind": "int", "width": 85},
    {"key": "growth", "label": "رشد نسبت به قبل", "kind": "text",
     "width": 130, "placeholder": "مثلاً ‎+۵٪"},
    {"key": "page_status", "label": "وضعیت صفحه", "kind": "combo",
     "options": SITE_PAGE_STATUSES, "width": 120},
    {"key": "note", "label": "توضیحات", "kind": "text",
     "stretch": True, "placeholder": "توضیحات (اختیاری)..."},
]


class SheetEditor(QWidget):
    """ویرایشگرِ جدولیِ یک شیت، وابسته به تاریخ و کارشناس."""

    def __init__(self, db: Session, technician, model, columns,
                 required_keys, title, hint, parent=None):
        super().__init__(parent)
        self.db = db
        self.technician = technician
        self.model = model
        self.columns = columns
        self.required_keys = required_keys
        self._title = title
        self._hint = hint
        self.setup_ui()
        self.load_data()

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        lbl = QLabel(self._hint)
        lbl.setObjectName("Muted")
        lbl.setWordWrap(True)
        top.addWidget(lbl, 1)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy/MM/dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self.load_data)

        btn_today = QPushButton("امروز")
        btn_today.setProperty("variant", "ghost")
        btn_today.setCursor(Qt.PointingHandCursor)
        btn_today.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))

        top.addWidget(QLabel("تاریخ گزارش:"))
        top.addWidget(self.date_edit)
        top.addWidget(btn_today)
        layout.addLayout(top)

        self.lbl_state = QLabel("")
        self.lbl_state.setObjectName("Muted")
        layout.addWidget(self.lbl_state)

        # نوار ابزار افزودن/حذف ردیف
        bar = QHBoxLayout()
        btn_add = QPushButton("+ افزودن ردیف")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(lambda: self.add_row())
        btn_del = QPushButton("حذف ردیف انتخاب‌شده")
        btn_del.setProperty("variant", "danger")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.clicked.connect(self.remove_selected_row)
        bar.addWidget(btn_add)
        bar.addWidget(btn_del)
        bar.addStretch()
        layout.addLayout(bar)

        # جدول
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels([c["label"] for c in self.columns])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(46)
        header = self.table.horizontalHeader()
        for i, col in enumerate(self.columns):
            if col.get("stretch"):
                header.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.Interactive)
                self.table.setColumnWidth(i, col.get("width", 110))
        layout.addWidget(self.table, 1)

        # پایین: ذخیره / حذف روز
        bottom = QHBoxLayout()
        btn_save = QPushButton("ذخیره‌ی گزارشِ این روز")
        btn_save.setProperty("variant", "success")
        btn_save.setMinimumHeight(42)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self.save)

        btn_delete = QPushButton("حذف گزارشِ این روز")
        btn_delete.setProperty("variant", "danger")
        btn_delete.setMinimumHeight(42)
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self.delete_day)

        bottom.addWidget(btn_save, 3)
        bottom.addWidget(btn_delete, 1)
        layout.addLayout(bottom)

    # ------------------------------------------------------- ساخت ویجت سلول
    def _make_widget(self, col, value=None):
        kind = col["kind"]
        if kind == "combo":
            w = QComboBox()
            w.addItem("—", "")  # گزینه‌ی خالی برای ردیف‌های پرنشده
            for opt in col["options"]:
                w.addItem(opt, opt)
            if value:
                idx = w.findData(value)
                if idx < 0:  # مقدار قدیمی/غیراستاندارد را هم حفظ کن
                    w.addItem(value, value)
                    idx = w.findData(value)
                w.setCurrentIndex(idx)
            return w
        if kind == "int":
            w = QLineEdit()
            w.setValidator(QIntValidator(0, 2_000_000_000, w))
            w.setAlignment(Qt.AlignCenter)
            w.setPlaceholderText("۰")
            if value is not None:
                w.setText(str(value))
            return w
        # text
        w = QLineEdit()
        w.setPlaceholderText(col.get("placeholder", ""))
        if value:
            w.setText(str(value))
        return w

    def _cell_value(self, row, i):
        col = self.columns[i]
        w = self.table.cellWidget(row, i)
        if w is None:
            return None
        if col["kind"] == "combo":
            return w.currentData() or None
        text = w.text().strip()
        if not text:
            return None
        if col["kind"] == "int":
            try:
                return int(text)
            except ValueError:
                return None
        return text

    # ------------------------------------------------------------ ردیف‌ها
    def add_row(self, values=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for i, col in enumerate(self.columns):
            val = None if values is None else getattr(values, col["key"], None)
            self.table.setCellWidget(row, i, self._make_widget(col, val))
        return row

    def remove_selected_row(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "توجه", "ابتدا یک ردیف را انتخاب کنید.")
            return
        self.table.removeRow(row)

    # ------------------------------------------------------------ داده‌ها
    def selected_date(self):
        return self.date_edit.date().toPython()

    def _query_rows(self, day):
        return (self.db.query(self.model)
                .filter(self.model.technician_id == self.technician.id,
                        self.model.report_date == day)
                .order_by(self.model.id)
                .all())

    def load_data(self):
        day = self.selected_date()
        rows = self._query_rows(day)
        self.table.setRowCount(0)
        for r in rows:
            self.add_row(r)
        if not rows:
            self.add_row()  # یک ردیف خالیِ آماده‌ی ورود
            self.lbl_state.setText("برای این تاریخ هنوز گزارشی ثبت نشده است — یک برگه‌ی جدید.")
        else:
            self.lbl_state.setText(
                f"{len(rows)} ردیفِ ثبت‌شده‌ی این روز بارگذاری شد؛ "
                "می‌توانید ویرایش کنید و دوباره ذخیره بزنید.")

    def _collect(self):
        """ردیف‌های پرشده را جمع می‌کند و در صورت نقص، خطا برمی‌گرداند.

        خروجی: (list[dict] | None). None یعنی خطا نمایش داده شده و باید متوقف شد.
        """
        collected = []
        for row in range(self.table.rowCount()):
            values = {}
            for i, col in enumerate(self.columns):
                values[col["key"]] = self._cell_value(row, i)
            # ردیفِ کاملاً خالی نادیده گرفته می‌شود
            if not any(v not in (None, "") for v in values.values()):
                continue
            for key in self.required_keys:
                if not values.get(key):
                    label = next(c["label"] for c in self.columns if c["key"] == key)
                    QMessageBox.warning(
                        self, "خطا",
                        f"ردیف {row + 1}: پر کردن «{label}» الزامی است.")
                    return None
            collected.append(values)
        return collected

    def save(self):
        day = self.selected_date()
        collected = self._collect()
        if collected is None:
            return
        if not collected:
            QMessageBox.warning(self, "خطا", "حداقل یک ردیف را کامل وارد کنید.")
            return

        # جایگزینی برگه‌ی همان روز (بدون رکورد تکراری)
        for old in self._query_rows(day):
            self.db.delete(old)
        self.db.flush()

        for values in collected:
            obj = self.model(
                technician_id=self.technician.id,
                technician_name_snapshot=self.technician.full_name,
                report_date=day,
                **values,
            )
            self.db.add(obj)

        self.db.commit()
        QMessageBox.information(
            self, "موفق",
            f"گزارش {day.strftime('%Y/%m/%d')} ذخیره شد. تعداد ردیف‌ها: {len(collected)}")
        self.load_data()

    def delete_day(self):
        day = self.selected_date()
        rows = self._query_rows(day)
        if not rows:
            QMessageBox.information(self, "توجه", "برای این تاریخ گزارشی ثبت نشده است.")
            return
        confirm = QMessageBox.question(
            self, "تأیید حذف",
            f"کل گزارشِ تاریخ {day.strftime('%Y/%m/%d')} حذف شود؟ این عملیات قابل بازگشت نیست.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        for r in rows:
            self.db.delete(r)
        self.db.commit()
        self.load_data()


class SitePage(QWidget):
    """صفحه‌ی واحد سایت با دو تبِ داخلی مطابق فایل مدیریت."""

    def __init__(self, db_session: Session, current_technician, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.technician = current_technician
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("واحد سایت")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.inner = QTabWidget()
        self.daily = SheetEditor(
            self.db, self.technician, SiteDailyActivity, DAILY_COLUMNS,
            required_keys=["platform", "description"],
            title="گزارش روزانه",
            hint="فعالیت‌های روزانه‌ی واحد سایت را ردیف‌به‌ردیف ثبت کنید.")
        self.network = SheetEditor(
            self.db, self.technician, SiteNetworkStat, NETWORK_COLUMNS,
            required_keys=["platform"],
            title="پایش شبکه‌ها",
            hint="آمار روزانه‌ی هر بستر (دنبال‌کننده، بازدید، تعامل و ...) را ثبت کنید.")

        self.inner.addTab(self.daily, "گزارش روزانه")
        self.inner.addTab(self.network, "پایش شبکه‌ها")
        layout.addWidget(self.inner, 1)

    def load_data(self):
        """با باز شدن تبِ واحد سایت، هر دو شیت تازه‌سازی می‌شوند."""
        self.daily.load_data()
        self.network.load_data()

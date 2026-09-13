from datetime import datetime, timedelta, date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QTextEdit, QFrame, QAbstractItemView, QMessageBox, QFileDialog,
    QComboBox, QDateEdit, QCheckBox
)
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session
from database.models import ServiceRecord, DEPARTMENTS
# export_records_to_excel به‌صورت تنبل داخل متد خروجی import می‌شود (سرعت استارتاپ)
from reports import summary
from ui.record_edit_dialog import EditServiceRecordDialog


def week_start(d):
    """شروع هفته (شنبه) برای یک تاریخ."""
    return d - timedelta(days=(d.weekday() - 5) % 7)


class RecordDetailDialog(QDialog):
    """پنجره‌ی نمایش جزئیات کامل یک برگه‌ی روزانه."""

    def __init__(self, record: ServiceRecord, parent=None):
        super().__init__(parent)
        self.setWindowTitle("جزئیات گزارش روزانه")
        self.setMinimumSize(520, 560)
        self.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(f"گزارش روزانه #{record.id}")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        info_frame = QFrame()
        info_frame.setObjectName("Card")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.addWidget(QLabel(f"<b>تاریخ:</b> {summary.date_text(record)}"))
        info_layout.addWidget(QLabel(f"<b>بخش:</b> {summary.dept_label(record)}"))
        info_layout.addWidget(QLabel(f"<b>کارشناس:</b> {record.technician_name_snapshot or '-'}"))
        info_layout.addWidget(QLabel(f"<b>مجموع خدمات:</b> {summary.total_count(record)}"))
        layout.addWidget(info_frame)

        layout.addWidget(QLabel("<b>خدمات کلی روز (با تعداد):</b>"))
        counted = QTextEdit()
        counted.setReadOnly(True)
        lines = [f"• {l.task.title if l.task else '؟'} — تعداد: {l.quantity or 1}"
                 + (f"  ({l.note})" if l.note else "")
                 for l in summary.counted_lines(record)]
        counted.setPlainText("\n".join(lines) if lines else "موردی ثبت نشده است.")
        layout.addWidget(counted)

        layout.addWidget(QLabel("<b>خدمات نام‌دار:</b>"))
        named = QTextEdit()
        named.setReadOnly(True)
        nlines = []
        for l in summary.named_lines(record):
            extras = " | ".join(x for x in [
                f"داخلی: {l.person_extension}" if l.person_extension else "",
                f"سیستم: {l.system_name}" if l.system_name else "",
                l.note or "",
            ] if x)
            nlines.append(f"• {l.task.title if l.task else '؟'} — {l.person_name}"
                          + (f"  ({extras})" if extras else ""))
        named.setPlainText("\n".join(nlines) if nlines else "موردی ثبت نشده است.")
        layout.addWidget(named)

        layout.addWidget(QLabel("<b>توضیح روز:</b>"))
        note_text = QTextEdit()
        note_text.setReadOnly(True)
        note_text.setPlainText(record.short_description or "بدون توضیح.")
        note_text.setMaximumHeight(70)
        layout.addWidget(note_text)

        btn_close = QPushButton("بستن")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class MyReportsPage(QWidget):
    def __init__(self, db_session: Session, current_technician):
        super().__init__()
        self.db = db_session
        self.technician = current_technician
        self.records = []       # همه‌ی برگه‌های کارشناس
        self.displayed = []     # برگه‌های در حال نمایش (پس از فیلتر)
        self.setup_ui()
        self.load_records()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ---------------- ردیف اول: عنوان و جستجو ----------------
        top_bar = QHBoxLayout()
        title = QLabel("گزارش‌های روزانه‌ی ثبت‌شده توسط من")
        title.setObjectName("PageTitle")
        top_bar.addWidget(title)
        top_bar.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو در خدمات، نام افراد، سیستم یا توضیحات...")
        self.txt_search.setFixedWidth(300)
        self.txt_search.textChanged.connect(self.filter_records)
        top_bar.addWidget(self.txt_search)

        btn_refresh = QPushButton("بروزرسانی")
        btn_refresh.setProperty("variant", "ghost")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.load_records)
        top_bar.addWidget(btn_refresh)

        layout.addLayout(top_bar)

        # ---------------- ردیف دوم: بازه‌ی زمانی و بخش ----------------
        date_bar = QHBoxLayout()
        self.cmb_period = QComboBox()
        for label, key in [
            ("همه‌ی زمان‌ها", "all"),
            ("امروز", "today"),
            ("دیروز", "yesterday"),
            ("۷ روز اخیر", "last7"),
            ("این هفته", "this_week"),
            ("هفته‌ی گذشته", "last_week"),
            ("این ماه", "this_month"),
            ("ماه گذشته", "last_month"),
            ("۳۰ روز اخیر", "last30"),
            ("بازه‌ی دلخواه", "custom"),
        ]:
            self.cmb_period.addItem(label, key)
        self.cmb_period.currentIndexChanged.connect(self._period_changed)

        self.cmb_dept = QComboBox()
        self.cmb_dept.addItem("همه‌ی بخش‌ها", None)
        for key, label in DEPARTMENTS:
            self.cmb_dept.addItem(label, key)
        self.cmb_dept.currentIndexChanged.connect(self.filter_records)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy/MM/dd")
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_from.dateChanged.connect(self.filter_records)
        self.date_from.setEnabled(False)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy/MM/dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self.filter_records)
        self.date_to.setEnabled(False)

        date_bar.addWidget(QLabel("بازه‌ی زمانی:"))
        date_bar.addWidget(self.cmb_period)
        date_bar.addWidget(QLabel("از:"))
        date_bar.addWidget(self.date_from)
        date_bar.addWidget(QLabel("تا:"))
        date_bar.addWidget(self.date_to)
        date_bar.addSpacing(16)
        date_bar.addWidget(QLabel("بخش:"))
        date_bar.addWidget(self.cmb_dept)
        date_bar.addStretch()
        layout.addLayout(date_bar)

        # ---------------- ردیف سوم: عملیات ----------------
        action_bar = QHBoxLayout()
        self.chk_select_all = QCheckBox("انتخاب همه")
        self.chk_select_all.stateChanged.connect(self._toggle_select_all)

        btn_edit = QPushButton("ویرایش")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(self.edit_selected)

        btn_delete_sel = QPushButton("حذف انتخاب‌شده‌ها")
        btn_delete_sel.setProperty("variant", "danger")
        btn_delete_sel.setCursor(Qt.PointingHandCursor)
        btn_delete_sel.clicked.connect(self.delete_checked)

        btn_export_sel = QPushButton("خروجی از انتخاب‌شده‌ها")
        btn_export_sel.setCursor(Qt.PointingHandCursor)
        btn_export_sel.clicked.connect(self.export_checked)

        btn_export_all = QPushButton("خروجی اکسل (همه‌ی نمایش)")
        btn_export_all.setProperty("variant", "success")
        btn_export_all.setCursor(Qt.PointingHandCursor)
        btn_export_all.clicked.connect(self.export_displayed)

        action_bar.addWidget(self.chk_select_all)
        action_bar.addStretch()
        action_bar.addWidget(btn_edit)
        action_bar.addWidget(btn_delete_sel)
        action_bar.addWidget(btn_export_sel)
        action_bar.addWidget(btn_export_all)
        layout.addLayout(action_bar)

        # ---------------- جدول ----------------
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "انتخاب", "ردیف", "کد رهگیری", "تاریخ", "بخش", "مجموع خدمات", "شرح خدمات روز"
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.show_record_details)

        header = self.table.horizontalHeader()
        for i in range(0, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)

        layout.addWidget(self.table, stretch=1)

        self.lbl_status = QLabel("تعداد کل گزارش‌های شما: ۰")
        self.lbl_status.setObjectName("Muted")
        layout.addWidget(self.lbl_status)

    # ---------------- بارگذاری ----------------
    def load_records(self):
        self.records = (
            self.db.query(ServiceRecord)
            .filter_by(technician_id=self.technician.id)
            .order_by(ServiceRecord.created_at.desc())
            .all()
        )
        self.records.sort(key=lambda r: summary.record_date(r) or date.min, reverse=True)
        self.filter_records()

    def show_record_details(self, index):
        row = index.row()
        if 0 <= row < len(self.displayed):
            RecordDetailDialog(self.displayed[row], self).exec()

    # ---------------- بازه‌ی زمانی ----------------
    def _period_changed(self):
        is_custom = self.cmb_period.currentData() == "custom"
        self.date_from.setEnabled(is_custom)
        self.date_to.setEnabled(is_custom)
        self.filter_records()

    def _date_range(self):
        key = self.cmb_period.currentData()
        today = datetime.now().date()
        if key == "all":
            return None
        if key == "today":
            start = end = today
        elif key == "yesterday":
            start = end = today - timedelta(days=1)
        elif key == "last7":
            start, end = today - timedelta(days=6), today
        elif key == "last30":
            start, end = today - timedelta(days=29), today
        elif key == "this_week":
            start, end = week_start(today), today
        elif key == "last_week":
            ws = week_start(today) - timedelta(days=7)
            start, end = ws, ws + timedelta(days=6)
        elif key == "this_month":
            start, end = today.replace(day=1), today
        elif key == "last_month":
            first_this = today.replace(day=1)
            last_prev = first_this - timedelta(days=1)
            start, end = last_prev.replace(day=1), last_prev
        elif key == "custom":
            start = self.date_from.date().toPython()
            end = self.date_to.date().toPython()
        else:
            return None
        return (start, end)

    # ---------------- فیلتر ----------------
    def filter_records(self, *_):
        query = self.txt_search.text().strip().lower()
        search_words = query.split() if query else []
        rng = self._date_range()
        dept = self.cmb_dept.currentData()

        filtered = []
        for rec in self.records:
            if dept and (rec.department or "IT") != dept:
                continue
            day = summary.record_date(rec)
            if rng and day is not None and not (rng[0] <= day <= rng[1]):
                continue
            if search_words:
                text = summary.searchable_text(rec)
                if not all(word in text for word in search_words):
                    continue
            filtered.append(rec)

        self.populate_table(filtered)

    def populate_table(self, records):
        self.displayed = list(records)
        self.chk_select_all.blockSignals(True)
        self.chk_select_all.setChecked(False)
        self.chk_select_all.blockSignals(False)

        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Unchecked)
            chk.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, chk)

            values = [
                str(row + 1),
                f"#{rec.id}",
                summary.date_text(rec),
                summary.dept_label(rec),
                str(summary.total_count(rec)),
                summary.summary_text(rec),
            ]
            for col, val in enumerate(values, start=1):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter if col < 6 else Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row, col, item)

        total = sum(summary.total_count(r) for r in records)
        self.lbl_status.setText(
            f"نمایش {len(records)} روز | مجموع خدمات: {total} | دابل‌کلیک روی ردیف برای جزئیات.")

    # ---------------- انتخاب ----------------
    def _toggle_select_all(self, state):
        check = Qt.Checked if state == Qt.Checked.value else Qt.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(check)

    def _checked_records(self):
        result = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked and row < len(self.displayed):
                result.append(self.displayed[row])
        return result

    def _selected_record(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.displayed):
            QMessageBox.information(self, "توجه", "لطفاً ابتدا یک گزارش را از جدول انتخاب کنید.")
            return None
        return self.displayed[row]

    # ---------------- عملیات ----------------
    def edit_selected(self):
        record = self._selected_record()
        if not record:
            return
        EditServiceRecordDialog(self.db, record, self).exec()
        self.load_records()

    def delete_checked(self):
        targets = self._checked_records()
        if not targets:
            QMessageBox.information(self, "توجه", "هیچ گزارشی انتخاب نشده است.")
            return
        confirm = QMessageBox.question(
            self, "تأیید حذف",
            f"آیا از حذف {len(targets)} گزارش انتخاب‌شده مطمئن هستید؟ این عملیات قابل بازگشت نیست.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        for rec in targets:
            for line in list(rec.tasks):
                self.db.delete(line)
            self.db.delete(rec)
        self.db.commit()
        QMessageBox.information(self, "موفق", f"{len(targets)} گزارش حذف شد.")
        self.load_records()

    def export_checked(self):
        targets = self._checked_records()
        if not targets:
            QMessageBox.information(self, "توجه", "هیچ گزارشی انتخاب نشده است.")
            return
        self._export(targets, "My_Reports_Selected.xlsx")

    def export_displayed(self):
        if not self.displayed:
            QMessageBox.warning(self, "خطا", "گزارشی برای خروجی گرفتن وجود ندارد.")
            return
        self._export(self.displayed, "My_Reports.xlsx")

    def _export(self, records, default_name):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل اکسل", default_name, "Excel Files (*.xlsx)"
        )
        if not filepath:
            return
        from reports.excel_exporter import export_records_to_excel
        try:
            export_records_to_excel(filepath, records, technician=self.technician)
            QMessageBox.information(self, "موفق", f"فایل اکسل ذخیره شد:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ایجاد فایل اکسل:\n{str(e)}")

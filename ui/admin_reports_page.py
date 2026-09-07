from datetime import datetime, timedelta, time

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QComboBox, QFileDialog, QMessageBox,
                               QAbstractItemView, QDialog, QDateEdit, QCheckBox)
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session
from database.models import ServiceRecord, Technician
from reports.excel_exporter import export_records_to_excel
from ui.record_edit_dialog import EditServiceRecordDialog, delete_service_record


def week_start(d):
    """شروع هفته (شنبه) برای یک تاریخ."""
    # weekday(): دوشنبه=0 ... یکشنبه=6 ؛ شنبه=5
    return d - timedelta(days=(d.weekday() - 5) % 7)


class AdminReportsPage(QWidget):
    def __init__(self, db_session: Session):
        super().__init__()
        self.db = db_session
        self.records = []
        self.all_records = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ---------------- ردیف اول: جستجو و فیلتر کارشناس ----------------
        top_bar = QHBoxLayout()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجوی سراسری (نام، داخلی، سیستم، عملیات)...")
        self.txt_search.textChanged.connect(self.filter_data)

        self.cmb_tech = QComboBox()
        self.cmb_tech.addItem("همه کارشناسان IT", None)
        self.cmb_tech.currentIndexChanged.connect(self.filter_data)

        top_bar.addWidget(QLabel("جستجو:"))
        top_bar.addWidget(self.txt_search, stretch=2)
        top_bar.addWidget(QLabel("کارشناس:"))
        top_bar.addWidget(self.cmb_tech, stretch=1)
        layout.addLayout(top_bar)

        # ---------------- ردیف دوم: بازه‌ی زمانی ----------------
        date_bar = QHBoxLayout()

        self.cmb_period = QComboBox()
        # (برچسب، کلید)
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

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy/MM/dd")
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_from.dateChanged.connect(self.filter_data)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy/MM/dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self.filter_data)

        # به‌صورت پیش‌فرض بازه‌ی دلخواه غیرفعال است
        self.date_from.setEnabled(False)
        self.date_to.setEnabled(False)

        date_bar.addWidget(QLabel("بازه‌ی زمانی:"))
        date_bar.addWidget(self.cmb_period)
        date_bar.addWidget(QLabel("از:"))
        date_bar.addWidget(self.date_from)
        date_bar.addWidget(QLabel("تا:"))
        date_bar.addWidget(self.date_to)
        date_bar.addStretch()
        layout.addLayout(date_bar)

        # ---------------- ردیف سوم: دکمه‌های عملیات ----------------
        action_bar = QHBoxLayout()

        self.chk_select_all = QCheckBox("انتخاب همه")
        self.chk_select_all.stateChanged.connect(self._toggle_select_all)

        btn_refresh = QPushButton("بروزرسانی")
        btn_refresh.setProperty("variant", "ghost")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.load_data)

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
        action_bar.addWidget(btn_refresh)
        action_bar.addWidget(btn_edit)
        action_bar.addWidget(btn_delete_sel)
        action_bar.addWidget(btn_export_sel)
        action_bar.addWidget(btn_export_all)
        layout.addLayout(action_bar)

        # ---------------- جدول ----------------
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "انتخاب", "ردیف", "کد رهگیری", "تاریخ", "ساعت",
            "مراجعه‌کننده", "داخلی", "سیستم", "کارشناس IT", "عملیات انجام‌شده"
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, 9):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Stretch)

        layout.addWidget(self.table, stretch=1)

        self.lbl_status = QLabel("تعداد رکوردها: ۰")
        self.lbl_status.setObjectName("Muted")
        layout.addWidget(self.lbl_status)

    # ---------------- بارگذاری داده ----------------
    def load_data(self):
        self.cmb_tech.blockSignals(True)
        current = self.cmb_tech.currentData()
        self.cmb_tech.clear()
        self.cmb_tech.addItem("همه کارشناسان IT", None)
        techs = self.db.query(Technician).filter_by(is_active=True).all()
        for t in techs:
            self.cmb_tech.addItem(t.full_name, t.id)
        # حفظ انتخاب قبلی در صورت امکان
        idx = self.cmb_tech.findData(current)
        if idx >= 0:
            self.cmb_tech.setCurrentIndex(idx)
        self.cmb_tech.blockSignals(False)

        self.all_records = (
            self.db.query(ServiceRecord)
            .order_by(ServiceRecord.created_at.desc())
            .all()
        )
        self.filter_data()

    # ---------------- منطق بازه‌ی زمانی ----------------
    def _period_changed(self):
        is_custom = self.cmb_period.currentData() == "custom"
        self.date_from.setEnabled(is_custom)
        self.date_to.setEnabled(is_custom)
        self.filter_data()

    def _date_range(self):
        """بازه‌ی (start, end) را بر اساس انتخاب کاربر برمی‌گرداند؛ None یعنی بدون محدودیت."""
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

        # به datetime تبدیل می‌کنیم تا کل روز پوشش داده شود
        return (datetime.combine(start, time.min), datetime.combine(end, time.max))

    # ---------------- فیلتر ----------------
    def filter_data(self):
        search_query = self.txt_search.text().strip().lower()
        search_words = search_query.split() if search_query else []
        selected_tech_id = self.cmb_tech.currentData()
        rng = self._date_range()

        self.records = []
        for rec in self.all_records:
            if selected_tech_id and rec.technician_id != selected_tech_id:
                continue

            if rng and rec.created_at is not None:
                if not (rng[0] <= rec.created_at <= rng[1]):
                    continue

            if search_words:
                tasks_str = " ".join([t.task.title for t in rec.tasks if t.task]).lower()
                searchable_text = (
                    f"{rec.id} {rec.requester_name_snapshot or ''} "
                    f"{rec.requester_extension_snapshot or ''} {rec.system_name_snapshot or ''} "
                    f"{rec.short_description or ''} {rec.technician_name_snapshot or ''} {tasks_str}"
                ).lower()
                if not all(word in searchable_text for word in search_words):
                    continue

            self.records.append(rec)

        self.populate_table(self.records)

    def populate_table(self, records):
        self.chk_select_all.blockSignals(True)
        self.chk_select_all.setChecked(False)
        self.chk_select_all.blockSignals(False)

        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            tasks_preview = " | ".join([t.task.title for t in rec.tasks if t.task]) or "-"

            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Unchecked)
            chk.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, chk)

            values = [
                str(row + 1),
                f"#{rec.id}",
                rec.created_at.strftime("%Y/%m/%d"),
                rec.created_at.strftime("%H:%M"),
                rec.requester_name_snapshot or "-",
                rec.requester_extension_snapshot or "-",
                rec.system_name_snapshot or "-",
                rec.technician_name_snapshot or "-",
                tasks_preview,
            ]
            for col, val in enumerate(values, start=1):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter if col < 9 else Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row, col, item)

        self.lbl_status.setText(f"تعداد رکوردهای در حال نمایش: {len(records)}")

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
            if item and item.checkState() == Qt.Checked and row < len(self.records):
                result.append(self.records[row])
        return result

    def _selected_record(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.records):
            QMessageBox.information(self, "توجه", "لطفاً ابتدا یک رکورد را از جدول انتخاب کنید.")
            return None
        return self.records[row]

    # ---------------- عملیات ----------------
    def edit_selected(self):
        record = self._selected_record()
        if not record:
            return
        dialog = EditServiceRecordDialog(self.db, record, self)
        if dialog.exec() == QDialog.Accepted:
            self.load_data()

    def delete_checked(self):
        targets = self._checked_records()
        if not targets:
            QMessageBox.information(self, "توجه", "هیچ رکوردی انتخاب نشده است.")
            return
        confirm = QMessageBox.question(
            self, "تأیید حذف",
            f"آیا از حذف {len(targets)} رکورد انتخاب‌شده مطمئن هستید؟ این عملیات قابل بازگشت نیست.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        for rec in targets:
            for st in list(rec.tasks):
                self.db.delete(st)
            self.db.delete(rec)
        self.db.commit()
        QMessageBox.information(self, "موفق", f"{len(targets)} رکورد حذف شد.")
        self.load_data()

    def export_checked(self):
        targets = self._checked_records()
        if not targets:
            QMessageBox.information(self, "توجه", "هیچ رکوردی انتخاب نشده است.")
            return
        self._export(targets, "IT_Reports_Selected.xlsx")

    def export_displayed(self):
        if not self.records:
            QMessageBox.warning(self, "خطا", "رکوردی برای خروجی گرفتن وجود ندارد.")
            return
        self._export(self.records, "IT_Reports.xlsx")

    def _export(self, records, default_name):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل اکسل", default_name, "Excel Files (*.xlsx)"
        )
        if not filepath:
            return
        try:
            selected_tech_id = self.cmb_tech.currentData()
            selected_tech = self.db.get(Technician, selected_tech_id) if selected_tech_id else None
            export_records_to_excel(filepath, records, technician=selected_tech)
            QMessageBox.information(self, "موفق", f"فایل اکسل با موفقیت ذخیره شد:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ایجاد فایل اکسل:\n{str(e)}")

"""گزارش جدا برای «خدمات نام‌دار» (ارتقا / اسمبل / نصب ویندوز و ...).

این خدمات مهم‌اند و نباید داخل گزارشِ کلیِ روز گم شوند؛ این‌جا هر مورد یک ردیفِ
مستقل با نام فرد است، با فیلتر، ویرایش، حذف و خروجی اکسل — مثل واحد IT.

  • حالت شخصی (admin=False): فقط خدماتِ نام‌دارِ همان کارشناس.
  • حالت مدیر (admin=True): همه‌ی کارشناسان + فیلترِ کارشناس.
"""
from datetime import datetime, timedelta

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                               QComboBox, QDateEdit, QFileDialog, QMessageBox,
                               QAbstractItemView, QCheckBox)
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session

from database.models import ServiceRecord, ServiceRecordTask, Technician
from reports import summary
from ui.record_edit_dialog import EditServiceRecordDialog

_PERIODS = [
    ("همه‌ی زمان‌ها", "all"), ("امروز", "today"), ("دیروز", "yesterday"),
    ("۷ روز اخیر", "last7"), ("این هفته", "this_week"), ("هفته‌ی گذشته", "last_week"),
    ("این ماه", "this_month"), ("ماه گذشته", "last_month"), ("۳۰ روز اخیر", "last30"),
    ("بازه‌ی دلخواه", "custom"),
]


def _week_start(d):
    return d - timedelta(days=(d.weekday() - 5) % 7)


class NamedServicesPage(QWidget):
    def __init__(self, db_session: Session, technician=None, admin=False, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.technician = technician
        self.admin = admin
        self.all_lines = []
        self.shown = []
        self.setup_ui()
        self.load_data()

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("گزارش خدمات نام‌دار" if self.admin else "خدمات نام‌دارِ من")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # فیلترها
        bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو در خدمت، نام فرد، سیستم، توضیح...")
        self.txt_search.textChanged.connect(self.apply_filters)
        bar.addWidget(QLabel("جستجو:"))
        bar.addWidget(self.txt_search, 2)

        self.cmb_tech = None
        if self.admin:
            self.cmb_tech = QComboBox()
            self.cmb_tech.addItem("همه کارشناسان", None)
            self.cmb_tech.currentIndexChanged.connect(self.apply_filters)
            bar.addWidget(QLabel("کارشناس:"))
            bar.addWidget(self.cmb_tech, 1)
        layout.addLayout(bar)

        bar2 = QHBoxLayout()
        self.cmb_period = QComboBox()
        for label, key in _PERIODS:
            self.cmb_period.addItem(label, key)
        self.cmb_period.currentIndexChanged.connect(self._period_changed)
        self.date_from = QDateEdit(); self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy/MM/dd")
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.dateChanged.connect(self.apply_filters); self.date_from.setEnabled(False)
        self.date_to = QDateEdit(); self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy/MM/dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self.apply_filters); self.date_to.setEnabled(False)
        bar2.addWidget(QLabel("بازه‌ی زمانی:")); bar2.addWidget(self.cmb_period)
        bar2.addWidget(QLabel("از:")); bar2.addWidget(self.date_from)
        bar2.addWidget(QLabel("تا:")); bar2.addWidget(self.date_to)
        bar2.addStretch()
        layout.addLayout(bar2)

        # عملیات
        action = QHBoxLayout()
        self.chk_all = QCheckBox("انتخاب همه")
        self.chk_all.stateChanged.connect(self._toggle_all)
        action.addWidget(self.chk_all)
        action.addStretch()

        btn_refresh = QPushButton("بروزرسانی"); btn_refresh.setProperty("variant", "ghost")
        btn_refresh.setCursor(Qt.PointingHandCursor); btn_refresh.clicked.connect(self.load_data)
        btn_edit = QPushButton("ویرایش"); btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(self.edit_selected)
        btn_del = QPushButton("حذف انتخاب‌شده‌ها"); btn_del.setProperty("variant", "danger")
        btn_del.setCursor(Qt.PointingHandCursor); btn_del.clicked.connect(self.delete_checked)
        btn_exp_sel = QPushButton("خروجی از انتخاب‌شده‌ها"); btn_exp_sel.setCursor(Qt.PointingHandCursor)
        btn_exp_sel.clicked.connect(self.export_checked)
        btn_exp_all = QPushButton("خروجی اکسل (همه‌ی نمایش)")
        btn_exp_all.setProperty("variant", "success"); btn_exp_all.setCursor(Qt.PointingHandCursor)
        btn_exp_all.clicked.connect(self.export_displayed)
        for b in (btn_refresh, btn_edit, btn_del, btn_exp_sel, btn_exp_all):
            action.addWidget(b)
        layout.addLayout(action)

        # جدول
        self.table = QTableWidget()
        headers = ["انتخاب", "ردیف", "تاریخ"]
        if self.admin:
            headers.append("کارشناس")
        headers += ["خدمت", "نام فرد", "داخلی", "سیستم", "توضیح"]
        self._headers = headers
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(lambda *_: self.edit_selected())
        header = self.table.horizontalHeader()
        for i in range(len(headers) - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(len(headers) - 1, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("Muted")
        layout.addWidget(self.lbl_status)

    # ------------------------------------------------------------ داده‌ها
    def load_data(self):
        if self.admin and self.cmb_tech is not None:
            self.cmb_tech.blockSignals(True)
            current = self.cmb_tech.currentData()
            self.cmb_tech.clear()
            self.cmb_tech.addItem("همه کارشناسان", None)
            for t in self.db.query(Technician).filter_by(is_active=True).all():
                self.cmb_tech.addItem(t.full_name, t.id)
            idx = self.cmb_tech.findData(current)
            if idx >= 0:
                self.cmb_tech.setCurrentIndex(idx)
            self.cmb_tech.blockSignals(False)

        q = (self.db.query(ServiceRecordTask)
             .join(ServiceRecord, ServiceRecord.id == ServiceRecordTask.service_record_id)
             .filter(ServiceRecordTask.person_name.isnot(None),
                     ServiceRecordTask.person_name != ""))
        if not self.admin and self.technician is not None:
            q = q.filter(ServiceRecord.technician_id == self.technician.id)
        lines = q.all()
        lines.sort(key=lambda l: (summary.record_date(l.record) or datetime.min.date(), l.id),
                   reverse=True)
        self.all_lines = lines
        self.apply_filters()

    def _period_changed(self):
        is_custom = self.cmb_period.currentData() == "custom"
        self.date_from.setEnabled(is_custom)
        self.date_to.setEnabled(is_custom)
        self.apply_filters()

    def _date_range(self):
        key = self.cmb_period.currentData()
        today = datetime.now().date()
        if key == "all":
            return None
        if key == "today":
            return today, today
        if key == "yesterday":
            y = today - timedelta(days=1); return y, y
        if key == "last7":
            return today - timedelta(days=6), today
        if key == "last30":
            return today - timedelta(days=29), today
        if key == "this_week":
            return _week_start(today), today
        if key == "last_week":
            ws = _week_start(today) - timedelta(days=7)
            return ws, ws + timedelta(days=6)
        if key == "this_month":
            return today.replace(day=1), today
        if key == "last_month":
            first_this = today.replace(day=1)
            last_prev = first_this - timedelta(days=1)
            return last_prev.replace(day=1), last_prev
        if key == "custom":
            return self.date_from.date().toPython(), self.date_to.date().toPython()
        return None

    def apply_filters(self, *_):
        query = self.txt_search.text().strip().lower()
        words = query.split() if query else []
        tech_id = self.cmb_tech.currentData() if (self.admin and self.cmb_tech) else None
        rng = self._date_range()

        shown = []
        for line in self.all_lines:
            rec = line.record
            if tech_id and (rec is None or rec.technician_id != tech_id):
                continue
            day = summary.record_date(rec) if rec else None
            if rng and day is not None and not (rng[0] <= day <= rng[1]):
                continue
            if words:
                text = " ".join([
                    (line.task.title if line.task else ""), line.person_name or "",
                    line.person_extension or "", line.system_name or "", line.note or "",
                    (rec.technician_name_snapshot if rec else "") or "",
                ]).lower()
                if not all(w in text for w in words):
                    continue
            shown.append(line)
        self.shown = shown
        self._fill()

    def _fill(self):
        self.chk_all.blockSignals(True); self.chk_all.setChecked(False); self.chk_all.blockSignals(False)
        self.table.setRowCount(len(self.shown))
        for row, line in enumerate(self.shown):
            rec = line.record
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Unchecked)
            chk.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, chk)

            vals = [str(row + 1), summary.date_text(rec) if rec else "-"]
            if self.admin:
                vals.append((rec.technician_name_snapshot if rec else None) or "-")
            vals += [line.task.title if line.task else "-", line.person_name or "-",
                     line.person_extension or "-", line.system_name or "-", line.note or "-"]
            for col, val in enumerate(vals, start=1):
                item = QTableWidgetItem(val)
                last = (col == len(vals))
                item.setTextAlignment((Qt.AlignRight if last else Qt.AlignCenter) | Qt.AlignVCenter)
                self.table.setItem(row, col, item)
        self.lbl_status.setText(f"تعداد خدمات نام‌دار: {len(self.shown)} | دابل‌کلیک برای ویرایش روز.")

    # ------------------------------------------------------------ انتخاب
    def _toggle_all(self, state):
        check = Qt.Checked if state == Qt.Checked.value else Qt.Unchecked
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            if it:
                it.setCheckState(check)

    def _checked(self):
        out = []
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            if it and it.checkState() == Qt.Checked and row < len(self.shown):
                out.append(self.shown[row])
        return out

    def _selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.shown):
            QMessageBox.information(self, "توجه", "ابتدا یک ردیف را انتخاب کنید.")
            return None
        return self.shown[row]

    # ------------------------------------------------------------ عملیات
    def edit_selected(self):
        line = self._selected()
        if not line or not line.record:
            return
        EditServiceRecordDialog(self.db, line.record, self).exec()
        self.load_data()

    def delete_checked(self):
        targets = self._checked()
        if not targets:
            QMessageBox.information(self, "توجه", "هیچ موردی انتخاب نشده است.")
            return
        confirm = QMessageBox.question(
            self, "تأیید حذف",
            f"آیا {len(targets)} خدمتِ نام‌دارِ انتخاب‌شده حذف شود؟ این عملیات قابل بازگشت نیست.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        for line in targets:
            self.db.delete(line)
        self.db.commit()
        QMessageBox.information(self, "موفق", f"{len(targets)} مورد حذف شد.")
        self.load_data()

    def export_checked(self):
        targets = self._checked()
        if not targets:
            QMessageBox.information(self, "توجه", "هیچ موردی انتخاب نشده است.")
            return
        self._export(targets, "Named_Services_Selected.xlsx")

    def export_displayed(self):
        if not self.shown:
            QMessageBox.warning(self, "خطا", "موردی برای خروجی گرفتن وجود ندارد.")
            return
        self._export(self.shown, "Named_Services.xlsx")

    def _export(self, lines, default_name):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل اکسل", default_name, "Excel Files (*.xlsx)")
        if not filepath:
            return
        from reports.excel_exporter import export_named_services_to_excel
        try:
            export_named_services_to_excel(
                filepath, lines,
                technician=self.technician if not self.admin else None)
            QMessageBox.information(self, "موفق", f"فایل اکسل ذخیره شد:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ایجاد فایل اکسل:\n{str(e)}")

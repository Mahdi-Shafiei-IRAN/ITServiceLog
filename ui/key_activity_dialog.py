"""افزودن / ویرایش یک «کار شاخص IT»."""
from datetime import date, datetime

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
                               QComboBox, QSpinBox, QDateEdit, QCheckBox, QPlainTextEdit,
                               QPushButton, QMessageBox)
from PySide6.QtCore import Qt, QDate

from database.models import (KeyActivity, KEY_STATUSES, KEY_STATUS_DONE,
                             KEY_STATUS_IN_PROGRESS, KEY_PRIORITIES, KEY_PRIORITY_NORMAL)
from services import key_activity_service as svc


def _qdate(d):
    return QDate(d.year, d.month, d.day)


class KeyActivityDialog(QDialog):
    def __init__(self, db, technician, activity=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.technician = technician
        self.activity = activity
        self.setWindowTitle("ویرایش کار شاخص" if activity else "کار شاخص جدید")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(520)
        self._build()
        self._load()
        self._connect()

    # ------------------------------------------------------------------ UI
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("مثلاً: راه‌اندازی سرور بکاپ")
        form.addRow("عنوان:", self.txt_title)

        # «کار یک‌روزه» فقط برای کار جدید: یک ذخیره و تمام
        self.chk_one_day = None
        if self.activity is None:
            self.chk_one_day = QCheckBox("کار یک‌روزه — انجام شد")
            form.addRow("", self.chk_one_day)

        self.cmb_category = QComboBox()
        self.cmb_category.setEditable(True)  # دسته‌ی جدید هم قابل تایپ است
        self.cmb_category.addItem("")
        self.cmb_category.addItems(svc.category_suggestions(self.db))
        form.addRow("دسته:", self.cmb_category)

        self.cmb_priority = QComboBox()
        self.cmb_priority.addItems(KEY_PRIORITIES)
        form.addRow("اهمیت:", self.cmb_priority)

        self.cmb_status = QComboBox()
        self.cmb_status.addItems(KEY_STATUSES)
        form.addRow("وضعیت:", self.cmb_status)

        self.spn_progress = QSpinBox()
        self.spn_progress.setRange(0, 100)
        self.spn_progress.setSuffix(" ٪")
        form.addRow("پیشرفت:", self.spn_progress)

        self.date_start = self._date_edit()
        form.addRow("تاریخ شروع:", self.date_start)

        end_row = QHBoxLayout()
        self.chk_has_end = QCheckBox("تاریخ اتمام دارد")
        self.date_end = self._date_edit()
        end_row.addWidget(self.chk_has_end)
        end_row.addWidget(self.date_end, 1)
        form.addRow("تاریخ اتمام:", end_row)

        self.txt_description = QPlainTextEdit()
        self.txt_description.setPlaceholderText("شرح کار...")
        self.txt_description.setFixedHeight(80)
        form.addRow("شرح:", self.txt_description)

        self.txt_result = QPlainTextEdit()
        self.txt_result.setPlaceholderText("نتیجه / دستاورد (اختیاری)...")
        self.txt_result.setFixedHeight(80)
        form.addRow("نتیجه:", self.txt_result)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_save = QPushButton("ذخیره")
        btn_save.setProperty("variant", "success")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("انصراف")
        btn_cancel.setProperty("variant", "ghost")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _date_edit(self):
        w = QDateEdit()
        w.setCalendarPopup(True)
        w.setDisplayFormat("yyyy/MM/dd")
        w.setDate(QDate.currentDate())
        return w

    def _load(self):
        a = self.activity
        if a is None:
            self.cmb_priority.setCurrentText(KEY_PRIORITY_NORMAL)
            self.cmb_status.setCurrentText(KEY_STATUS_IN_PROGRESS)
        else:
            self.txt_title.setText(a.title or "")
            self.cmb_category.setCurrentText(a.category or "")
            self.cmb_priority.setCurrentText(a.priority or KEY_PRIORITY_NORMAL)
            self.cmb_status.setCurrentText(a.status or KEY_STATUS_IN_PROGRESS)
            self.spn_progress.setValue(a.progress or 0)
            if a.start_date:
                self.date_start.setDate(_qdate(a.start_date))
            if a.end_date:
                self.chk_has_end.setChecked(True)
                self.date_end.setDate(_qdate(a.end_date))
            self.txt_description.setPlainText(a.description or "")
            self.txt_result.setPlainText(a.result or "")
        self.date_end.setEnabled(self.chk_has_end.isChecked())
        self._last_status = self.cmb_status.currentText()

    def _connect(self):
        # بعد از بارگذاری وصل می‌شوند تا مقداردهی اولیه قاعده‌ها را اجرا نکند
        self.cmb_status.currentTextChanged.connect(self._on_status_changed)
        self.chk_has_end.toggled.connect(self._on_has_end)
        self.date_start.dateChanged.connect(self._on_start_changed)
        if self.chk_one_day is not None:
            self.chk_one_day.toggled.connect(self._on_one_day)

    # ------------------------------------------------------------ قاعده‌ها
    def _one_day(self):
        return self.chk_one_day is not None and self.chk_one_day.isChecked()

    def _on_status_changed(self, status):
        """همان قاعده‌ی apply_status در سرویس، روی فرم.

        ورود به یک وضعیت بسته (انجام‌شده یا لغوشده) ← اگر تیک «تاریخ اتمام دارد»
        خورده نبود، با تاریخ امروز خورده می‌شود؛ فقط «انجام شد» پیشرفت را هم
        ۱۰۰ می‌کند. خروج از وضعیت بسته به یک وضعیت باز ← تیک برداشته می‌شود.
        جابه‌جایی بین دو وضعیت بسته چیزی را تغییر نمی‌دهد.
        """
        if svc.is_closed_status(status):
            if status == KEY_STATUS_DONE:
                self.spn_progress.setValue(100)
            if not self.chk_has_end.isChecked():
                self.chk_has_end.setChecked(True)
                self.date_end.setDate(QDate.currentDate())
        elif svc.is_closed_status(self._last_status):
            self.chk_has_end.setChecked(False)
        self._last_status = status

    def _on_has_end(self, checked):
        self.date_end.setEnabled(checked and not self._one_day())

    def _on_start_changed(self, *_):
        if self._one_day():
            self.date_end.setDate(self.date_start.date())

    def _on_one_day(self, checked):
        if checked:
            self.cmb_status.setCurrentText(KEY_STATUS_DONE)
            self.chk_has_end.setChecked(True)
            self.date_end.setDate(self.date_start.date())
        for w in (self.cmb_status, self.spn_progress, self.chk_has_end):
            w.setEnabled(not checked)
        self.date_end.setEnabled(self.chk_has_end.isChecked() and not checked)

    # ------------------------------------------------------------ ذخیره
    def values(self):
        status = self.cmb_status.currentText()
        progress = self.spn_progress.value()
        end = self.date_end.date().toPython() if self.chk_has_end.isChecked() else None
        return {
            "title": self.txt_title.text().strip(),
            "category": self.cmb_category.currentText().strip() or None,
            "priority": self.cmb_priority.currentText(),
            "status": status,
            "progress": progress,
            "start_date": self.date_start.date().toPython(),
            "end_date": end,
            "description": self.txt_description.toPlainText().strip() or None,
            "result": self.txt_result.toPlainText().strip() or None,
        }

    def save(self):
        vals = self.values()
        errors = svc.validate_activity(vals["title"], vals["start_date"],
                                       vals["end_date"], vals["progress"])
        if errors:
            QMessageBox.warning(self, "خطا", "\n".join(errors))
            return False
        act = self.activity
        try:
            if act is None:
                act = KeyActivity(technician_id=self.technician.id,
                                  technician_name_snapshot=self.technician.full_name)
                self.db.add(act)
            # قاعده‌ی وضعیت «انجام شد» تنها در سرویس تعریف می‌شود
            status = vals.pop("status")
            for key, value in vals.items():
                setattr(act, key, value)
            svc.apply_status(act, status, date.today())
            act.updated_at = datetime.now()
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            QMessageBox.critical(self, "خطا", f"ذخیره‌ی کار شاخص ممکن نشد:\n{exc}")
            return False
        self.activity = act
        self.accept()
        return True

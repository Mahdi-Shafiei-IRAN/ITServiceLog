"""ویرایش یک ردیفِ واحد سایت (گزارش روزانه یا پایش شبکه‌ها)."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                               QLineEdit, QComboBox, QPushButton, QDateEdit, QMessageBox)
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session


class SiteRowEditDialog(QDialog):
    def __init__(self, db: Session, row, columns, title="ویرایش ردیف", parent=None):
        super().__init__(parent)
        self.db = db
        self.row = row
        self.columns = columns
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(440)
        self._widgets = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy/MM/dd")
        d = self.row.report_date
        self.date_edit.setDate(QDate(d.year, d.month, d.day) if d else QDate.currentDate())
        form.addRow("تاریخ:", self.date_edit)

        for col in self.columns:
            w = self._make_widget(col, getattr(self.row, col["key"], None))
            self._widgets[col["key"]] = w
            form.addRow(col["label"] + ":", w)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_save = QPushButton("ذخیره تغییرات")
        btn_save.setProperty("variant", "success")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton("انصراف")
        btn_cancel.setProperty("variant", "ghost")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _make_widget(self, col, value):
        kind = col["kind"]
        if kind == "combo":
            w = QComboBox()
            w.addItem("—", "")
            for opt in col["options"]:
                w.addItem(opt, opt)
            if value:
                idx = w.findData(value)
                if idx < 0:
                    w.addItem(value, value); idx = w.findData(value)
                w.setCurrentIndex(idx)
            return w
        if kind == "int":
            w = QLineEdit()
            w.setValidator(QIntValidator(0, 2_000_000_000, w))
            if value is not None:
                w.setText(str(value))
            return w
        w = QLineEdit()
        if value:
            w.setText(str(value))
        return w

    def _value(self, col):
        w = self._widgets[col["key"]]
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

    def _save(self):
        self.row.report_date = self.date_edit.date().toPython()
        for col in self.columns:
            setattr(self.row, col["key"], self._value(col))
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "خطا", f"ذخیره نشد:\n{e}")
            return
        self.accept()

"""دیالوگ ویرایش یک برگه‌ی گزارش روزانه (استفاده مشترک مدیر و کارشناس)."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session

from database.models import ServiceRecord, DEPT_LABELS
from ui.daily_entry_page import DailyEntryPage


class EditServiceRecordDialog(QDialog):
    """همان صفحه‌ی ثبت روزانه را در حالت ویرایش یک روز مشخص باز می‌کند."""

    def __init__(self, db: Session, record: ServiceRecord, parent=None):
        super().__init__(parent)
        self.db = db
        self.record = record
        dept_label = DEPT_LABELS.get(record.department, record.department or "")
        self.setWindowTitle(f"ویرایش گزارش روزانه #{record.id} — {dept_label}")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumSize(1000, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(
            f"کارشناس: {record.technician_name_snapshot or '-'} | "
            f"بخش: {dept_label} | کد گزارش: #{record.id}")
        header.setObjectName("Muted")
        header.setContentsMargins(20, 12, 20, 0)
        layout.addWidget(header)

        self.page = DailyEntryPage(db, record.technician, record.department, self)
        if record.report_date:
            self.page.date_edit.setDate(QDate(record.report_date.year,
                                              record.report_date.month,
                                              record.report_date.day))
        # تاریخ در حالت ویرایش قفل است تا برگه‌ی روز دیگری بازنویسی نشود
        self.page.date_edit.setEnabled(False)
        layout.addWidget(self.page, 1)

        btns = QHBoxLayout()
        btns.setContentsMargins(20, 0, 20, 16)
        btn_close = QPushButton("بستن و بازگشت")
        btn_close.setProperty("variant", "ghost")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(btn_close)
        layout.addLayout(btns)


def delete_service_record(db: Session, record: ServiceRecord, parent=None) -> bool:
    """حذف یک برگه‌ی گزارش پس از تأیید کاربر. در صورت حذف True برمی‌گرداند."""
    confirm = QMessageBox.question(
        parent, "تأیید حذف",
        f"آیا از حذف گزارش #{record.id} مطمئن هستید؟ این عملیات قابل بازگشت نیست.",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    if confirm != QMessageBox.Yes:
        return False
    for line in list(record.tasks):
        db.delete(line)
    db.delete(record)
    db.commit()
    return True

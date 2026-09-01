"""دیالوگ ویرایش یک گزارش مراجعه (استفاده مشترک مدیر و کارشناس)."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QTextEdit, QTreeWidget, QTreeWidgetItem, QPushButton,
                               QGroupBox, QMessageBox)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from database.models import Task, ServiceRecord, ServiceRecordTask


class EditServiceRecordDialog(QDialog):
    def __init__(self, db: Session, record: ServiceRecord, parent=None):
        super().__init__(parent)
        self.db = db
        self.record = record
        self.setWindowTitle(f"ویرایش گزارش #{record.id}")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumSize(540, 640)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(f"ویرایش گزارش #{self.record.id}")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        # مراجعه‌کننده
        req_group = QGroupBox("مراجعه‌کننده")
        req_layout = QHBoxLayout()
        self.txt_name = QLineEdit(); self.txt_name.setPlaceholderText("نام شخص...")
        self.txt_ext = QLineEdit(); self.txt_ext.setPlaceholderText("داخلی...")
        self.txt_system = QLineEdit(); self.txt_system.setPlaceholderText("سیستم / IP...")
        req_layout.addWidget(QLabel("نام:")); req_layout.addWidget(self.txt_name, 2)
        req_layout.addWidget(QLabel("داخلی:")); req_layout.addWidget(self.txt_ext, 1)
        req_layout.addWidget(QLabel("سیستم:")); req_layout.addWidget(self.txt_system, 1)
        req_group.setLayout(req_layout)
        layout.addWidget(req_group)

        # عملیات
        task_group = QGroupBox("عملیات انجام‌شده")
        task_layout = QVBoxLayout()
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True)
        task_layout.addWidget(self.tree)
        task_group.setLayout(task_layout)
        layout.addWidget(task_group, 1)

        # توضیحات
        self.txt_notes = QTextEdit(); self.txt_notes.setPlaceholderText("توضیح کوتاه...")
        self.txt_notes.setMaximumHeight(80)
        layout.addWidget(self.txt_notes)

        # دکمه‌ها
        btns = QHBoxLayout()
        btn_save = QPushButton("ذخیره تغییرات")
        btn_save.setProperty("variant", "success")
        btn_save.setMinimumHeight(40)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("انصراف")
        btn_cancel.setProperty("variant", "ghost")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_save, 2)
        btns.addWidget(btn_cancel, 1)
        layout.addLayout(btns)

    def _load(self):
        self.txt_name.setText(self.record.requester_name_snapshot or "")
        self.txt_ext.setText(self.record.requester_extension_snapshot or "")
        self.txt_system.setText(self.record.system_name_snapshot or "")
        self.txt_notes.setPlainText(self.record.short_description or "")

        checked_ids = {t.task_id for t in self.record.tasks}
        self.tree.clear()
        top_tasks = self.db.query(Task).filter_by(parent_task_id=None, is_active=True).all()
        for task in top_tasks:
            item = QTreeWidgetItem(self.tree, [task.title])
            item.setData(0, Qt.UserRole, task.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if task.id in checked_ids else Qt.Unchecked)
            self._add_sub_tasks(item, task, checked_ids)
        self.tree.expandAll()

    def _add_sub_tasks(self, parent_item, parent_task, checked_ids):
        for sub in parent_task.sub_tasks:
            if not sub.is_active:
                continue
            child = QTreeWidgetItem(parent_item, [sub.title])
            child.setData(0, Qt.UserRole, sub.id)
            child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
            child.setCheckState(0, Qt.Checked if sub.id in checked_ids else Qt.Unchecked)
            self._add_sub_tasks(child, sub, checked_ids)

    def _get_checked(self, root=None, acc=None):
        if acc is None:
            acc = []
        count = self.tree.topLevelItemCount() if root is None else root.childCount()
        for i in range(count):
            item = self.tree.topLevelItem(i) if root is None else root.child(i)
            if item.checkState(0) == Qt.Checked:
                acc.append(item.data(0, Qt.UserRole))
            self._get_checked(item, acc)
        return acc

    def save(self):
        name = self.txt_name.text().strip()
        tasks = self._get_checked()
        if not name or not tasks:
            QMessageBox.warning(self, "خطا", "نام شخص و انتخاب حداقل یک عملیات الزامی است.")
            return

        self.record.requester_name_snapshot = name
        self.record.requester_extension_snapshot = self.txt_ext.text().strip()
        self.record.system_name_snapshot = self.txt_system.text().strip()
        self.record.short_description = self.txt_notes.toPlainText()

        # بازسازی لیست عملیات
        for st in list(self.record.tasks):
            self.db.delete(st)
        self.db.flush()
        for task_id in tasks:
            self.db.add(ServiceRecordTask(service_record_id=self.record.id, task_id=task_id))

        self.db.commit()
        QMessageBox.information(self, "موفق", "تغییرات با موفقیت ذخیره شد.")
        self.accept()


def delete_service_record(db: Session, record: ServiceRecord, parent=None) -> bool:
    """حذف یک گزارش پس از تأیید کاربر. در صورت حذف True برمی‌گرداند."""
    confirm = QMessageBox.question(
        parent, "تأیید حذف",
        f"آیا از حذف گزارش #{record.id} مطمئن هستید؟ این عملیات قابل بازگشت نیست.",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    if confirm != QMessageBox.Yes:
        return False
    for st in list(record.tasks):
        db.delete(st)
    db.delete(record)
    db.commit()
    return True

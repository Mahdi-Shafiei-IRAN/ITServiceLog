from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from database.models import Task

class TasksPage(QWidget):
    def __init__(self, db_session: Session):
        super().__init__()
        self.db = db_session
        self.setup_ui()
        self.load_tasks()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("مدیریت خدمات و عملیات IT")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # فرم افزودن
        form_layout = QHBoxLayout()
        form_layout.setSpacing(8)
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("عنوان خدمت یا دسته‌بندی جدید...")

        btn_add_main = QPushButton("+ افزودن دسته اصلی")
        btn_add_main.setCursor(Qt.PointingHandCursor)
        btn_add_main.clicked.connect(lambda: self.add_task(is_main=True))

        btn_add_sub = QPushButton("+ افزودن زیرمجموعه به آیتم انتخاب‌شده")
        btn_add_sub.setProperty("variant", "ghost")
        btn_add_sub.setCursor(Qt.PointingHandCursor)
        btn_add_sub.clicked.connect(lambda: self.add_task(is_main=False))

        form_layout.addWidget(self.txt_title)
        form_layout.addWidget(btn_add_main)
        form_layout.addWidget(btn_add_sub)
        layout.addLayout(form_layout)

        # درخت نمایش خدمات
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("لیست خدمات و عملیات IT (برای افزودن زیرمجموعه، یک مورد را انتخاب کنید)")
        layout.addWidget(self.tree)

    def load_tasks(self):
        self.tree.clear()
        # گرفتن فقط دسته‌های اصلی
        top_tasks = self.db.query(Task).filter_by(parent_task_id=None, is_active=True).all()
        for task in top_tasks:
            item = QTreeWidgetItem(self.tree, [task.title])
            item.setData(0, Qt.UserRole, task.id)
            self._load_sub_tasks(item, task)
        self.tree.expandAll()

    def _load_sub_tasks(self, parent_item, parent_task):
        for sub in parent_task.sub_tasks:
            if sub.is_active:
                child = QTreeWidgetItem(parent_item, [sub.title])
                child.setData(0, Qt.UserRole, sub.id)
                self._load_sub_tasks(child, sub)

    def add_task(self, is_main=True):
        title = self.txt_title.text().strip()
        if not title:
            return QMessageBox.warning(self, "خطا", "لطفاً عنوان را وارد کنید.")

        parent_id = None
        if not is_main:
            selected = self.tree.currentItem()
            if not selected:
                return QMessageBox.warning(self, "خطا", "برای افزودن زیرمجموعه، یک مورد را از لیست پایین انتخاب کنید.")
            parent_id = selected.data(0, Qt.UserRole)

        new_task = Task(title=title, parent_task_id=parent_id)
        self.db.add(new_task)
        self.db.commit()
        
        self.txt_title.clear()
        self.load_tasks()
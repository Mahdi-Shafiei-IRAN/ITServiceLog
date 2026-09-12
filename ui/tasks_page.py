from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
                               QMessageBox, QComboBox, QCheckBox, QInputDialog)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from database.models import Task, ServiceRecordTask, DEPARTMENTS, DEPT_IT


class TasksPage(QWidget):
    """مدیریت درخت خدمات، به تفکیک بخش (IT / سایت) با امکان ویرایش و حذف."""

    def __init__(self, db_session: Session):
        super().__init__()
        self.db = db_session
        self.setup_ui()
        self.load_tasks()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("مدیریت خدمات و عملیات")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # انتخاب بخش
        dept_bar = QHBoxLayout()
        self.cmb_dept = QComboBox()
        for key, label in DEPARTMENTS:
            self.cmb_dept.addItem(label, key)
        self.cmb_dept.currentIndexChanged.connect(self.load_tasks)
        dept_bar.addWidget(QLabel("بخش:"))
        dept_bar.addWidget(self.cmb_dept)
        dept_bar.addStretch()
        layout.addLayout(dept_bar)

        # فرم افزودن
        form_layout = QHBoxLayout()
        form_layout.setSpacing(8)
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("عنوان خدمت یا دسته‌بندی جدید...")

        self.chk_requires_name = QCheckBox("نیاز به نام فرد دارد (تک‌تک ثبت می‌شود)")
        self.chk_requires_name.setToolTip(
            "برای خدماتی مثل ارتقا، اسمبل سیستم و نصب ویندوز که باید جداگانه و با نام ثبت شوند.")

        btn_add_main = QPushButton("+ افزودن دسته اصلی")
        btn_add_main.setCursor(Qt.PointingHandCursor)
        btn_add_main.clicked.connect(lambda: self.add_task(is_main=True))

        btn_add_sub = QPushButton("+ افزودن زیرمجموعه به آیتم انتخاب‌شده")
        btn_add_sub.setProperty("variant", "ghost")
        btn_add_sub.setCursor(Qt.PointingHandCursor)
        btn_add_sub.clicked.connect(lambda: self.add_task(is_main=False))

        form_layout.addWidget(self.txt_title, stretch=2)
        form_layout.addWidget(self.chk_requires_name)
        form_layout.addWidget(btn_add_main)
        form_layout.addWidget(btn_add_sub)
        layout.addLayout(form_layout)

        # نوار عملیات روی آیتم انتخاب‌شده
        action_bar = QHBoxLayout()

        btn_up = QPushButton("▲ بالا")
        btn_up.setToolTip("انتقال مورد انتخاب‌شده به بالا (اولویت بیشتر)")
        btn_up.setProperty("variant", "ghost")
        btn_up.setCursor(Qt.PointingHandCursor)
        btn_up.clicked.connect(self.move_up)

        btn_down = QPushButton("▼ پایین")
        btn_down.setToolTip("انتقال مورد انتخاب‌شده به پایین (اولویت کمتر)")
        btn_down.setProperty("variant", "ghost")
        btn_down.setCursor(Qt.PointingHandCursor)
        btn_down.clicked.connect(self.move_down)

        action_bar.addWidget(btn_up)
        action_bar.addWidget(btn_down)

        btn_rename = QPushButton("ویرایش عنوان")
        btn_rename.setCursor(Qt.PointingHandCursor)
        btn_rename.clicked.connect(self.rename_task)

        btn_toggle_name = QPushButton("تغییر حالت «نیاز به نام»")
        btn_toggle_name.setProperty("variant", "ghost")
        btn_toggle_name.setCursor(Qt.PointingHandCursor)
        btn_toggle_name.clicked.connect(self.toggle_requires_name)

        btn_move = QPushButton("انتقال به بخش دیگر")
        btn_move.setProperty("variant", "ghost")
        btn_move.setCursor(Qt.PointingHandCursor)
        btn_move.clicked.connect(self.move_department)

        btn_delete = QPushButton("حذف")
        btn_delete.setProperty("variant", "danger")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self.delete_task)

        action_bar.addStretch()
        action_bar.addWidget(btn_rename)
        action_bar.addWidget(btn_toggle_name)
        action_bar.addWidget(btn_move)
        action_bar.addWidget(btn_delete)
        layout.addLayout(action_bar)

        # درخت نمایش خدمات
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["عنوان خدمت", "نحوه‌ی ثبت"])
        self.tree.setColumnWidth(0, 520)
        self.tree.itemDoubleClicked.connect(lambda *_: self.rename_task())
        layout.addWidget(self.tree)

        hint = QLabel("ابتدا یک مورد را از درخت انتخاب کنید، سپس با دکمه‌های ▲/▼ اولویت آن را "
                      "جابه‌جا کنید یا ویرایش/حذف بزنید.")
        hint.setObjectName("Muted")
        layout.addWidget(hint)

    # ---------------- بارگذاری ----------------
    def current_department(self):
        return self.cmb_dept.currentData() or DEPT_IT

    def load_tasks(self):
        dept = self.current_department()
        selected_id = self._selected_id()
        self.tree.clear()
        top_tasks = (self.db.query(Task)
                     .filter(Task.parent_task_id.is_(None),
                             Task.is_active.is_(True),
                             Task.department == dept)
                     .order_by(Task.position, Task.id)
                     .all())
        for task in top_tasks:
            item = self._make_item(self.tree, task)
            self._load_sub_tasks(item, task)
        self.tree.expandAll()
        if selected_id:
            self._select_by_id(selected_id)

    def _make_item(self, parent, task):
        mode = "تک‌تک با نام" if task.requires_name else "شمارش روزانه"
        item = QTreeWidgetItem(parent, [task.title, mode])
        item.setData(0, Qt.UserRole, task.id)
        return item

    def _load_sub_tasks(self, parent_item, parent_task):
        for sub in self._ordered_children(parent_task):
            if sub.is_active:
                child = self._make_item(parent_item, sub)
                self._load_sub_tasks(child, sub)

    @staticmethod
    def _ordered_children(parent_task):
        return sorted(parent_task.sub_tasks, key=lambda t: ((t.position or 0), t.id))

    def _selected_id(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def _select_by_id(self, task_id):
        def walk(item):
            if item.data(0, Qt.UserRole) == task_id:
                self.tree.setCurrentItem(item)
                return True
            return any(walk(item.child(i)) for i in range(item.childCount()))
        for i in range(self.tree.topLevelItemCount()):
            if walk(self.tree.topLevelItem(i)):
                return

    def _selected_task(self):
        task_id = self._selected_id()
        if not task_id:
            QMessageBox.information(self, "توجه", "ابتدا یک مورد را از درخت انتخاب کنید.")
            return None
        return self.db.get(Task, task_id)

    # ---------------- عملیات ----------------
    def add_task(self, is_main=True):
        title = self.txt_title.text().strip()
        if not title:
            return QMessageBox.warning(self, "خطا", "لطفاً عنوان را وارد کنید.")

        parent_id = None
        if not is_main:
            selected = self.tree.currentItem()
            if not selected:
                return QMessageBox.warning(
                    self, "خطا", "برای افزودن زیرمجموعه، یک مورد را از لیست پایین انتخاب کنید.")
            parent_id = selected.data(0, Qt.UserRole)

        self.db.add(Task(
            title=title,
            parent_task_id=parent_id,
            department=self.current_department(),
            requires_name=self.chk_requires_name.isChecked(),
            position=self._next_position(parent_id),
        ))
        self.db.commit()

        self.txt_title.clear()
        self.chk_requires_name.setChecked(False)
        self.load_tasks()

    def _siblings(self, parent_id):
        """هم‌ردیف‌های یک آیتم (هم‌بخش و هم‌والد)، مرتب‌شده بر اساس اولویت."""
        return (self.db.query(Task)
                .filter(Task.parent_task_id == parent_id if parent_id
                        else Task.parent_task_id.is_(None),
                        Task.is_active.is_(True),
                        Task.department == self.current_department())
                .order_by(Task.position, Task.id)
                .all())

    def _next_position(self, parent_id):
        sibs = self._siblings(parent_id)
        return (max((s.position or 0) for s in sibs) + 1) if sibs else 1

    def move_up(self):
        self._move(-1)

    def move_down(self):
        self._move(1)

    def _move(self, delta):
        task = self._selected_task()
        if not task:
            return
        sibs = self._siblings(task.parent_task_id)
        # اطمینان از یکتا بودن مقادیر position پیش از جابه‌جایی
        for i, s in enumerate(sibs, start=1):
            s.position = i
        idx = next((i for i, s in enumerate(sibs) if s.id == task.id), None)
        if idx is None:
            return
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(sibs):
            return  # به ابتدا/انتهای لیست رسیده‌ایم
        other = sibs[new_idx]
        task.position, other.position = other.position, task.position
        self.db.commit()
        self.load_tasks()
        self._select_by_id(task.id)

    def rename_task(self):
        task = self._selected_task()
        if not task:
            return
        new_title, ok = QInputDialog.getText(self, "ویرایش عنوان", "عنوان جدید:", text=task.title)
        new_title = (new_title or "").strip()
        if not ok or not new_title or new_title == task.title:
            return
        task.title = new_title
        self.db.commit()
        self.load_tasks()

    def toggle_requires_name(self):
        task = self._selected_task()
        if not task:
            return
        task.requires_name = not bool(task.requires_name)
        self.db.commit()
        state = "تک‌تک با نام فرد" if task.requires_name else "شمارش کلی روزانه"
        QMessageBox.information(self, "انجام شد", f"«{task.title}» از این پس {state} ثبت می‌شود.")
        self.load_tasks()

    def move_department(self):
        task = self._selected_task()
        if not task:
            return
        if task.parent_task_id:
            QMessageBox.information(
                self, "توجه",
                "فقط دسته‌های اصلی قابل انتقال هستند؛ زیرمجموعه‌ها همراه پدرشان منتقل می‌شوند.")
            return
        labels = [label for _, label in DEPARTMENTS]
        keys = [key for key, _ in DEPARTMENTS]
        current = keys.index(task.department or DEPT_IT)
        choice, ok = QInputDialog.getItem(self, "انتقال بخش", "بخش مقصد:", labels, current, False)
        if not ok:
            return
        self._set_department_recursive(task, keys[labels.index(choice)])
        self.db.commit()
        self.load_tasks()

    def _set_department_recursive(self, task, dept):
        task.department = dept
        for sub in task.sub_tasks:
            self._set_department_recursive(sub, dept)

    def delete_task(self):
        task = self._selected_task()
        if not task:
            return

        ids = []
        self._collect_ids(task, ids)
        used = (self.db.query(ServiceRecordTask)
                .filter(ServiceRecordTask.task_id.in_(ids)).count())

        extra = ""
        if used:
            extra = (f"\n\nاین مورد در {used} گزارش ثبت‌شده استفاده شده است؛ "
                     "برای حفظ سوابق، به‌جای حذف کامل فقط از لیست‌ها پنهان می‌شود.")
        confirm = QMessageBox.question(
            self, "تأیید حذف",
            f"«{task.title}» و {len(ids) - 1} زیرمجموعه‌اش حذف شود؟{extra}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return

        if used:
            self._deactivate_recursive(task)
        else:
            self._delete_recursive(task)
        self.db.commit()
        self.load_tasks()

    def _collect_ids(self, task, acc):
        acc.append(task.id)
        for sub in task.sub_tasks:
            self._collect_ids(sub, acc)

    def _deactivate_recursive(self, task):
        task.is_active = False
        for sub in task.sub_tasks:
            self._deactivate_recursive(sub)

    def _delete_recursive(self, task):
        for sub in list(task.sub_tasks):
            self._delete_recursive(sub)
        self.db.delete(task)

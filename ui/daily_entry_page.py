"""ثبت گزارش روزانه، به تفکیک بخش (IT / سایت).

به‌جای ثبت دانه‌دانه‌ی هر مراجعه، هر کارشناس برای هر روز یک «برگه‌ی روزانه» دارد:
  • خدمات کلی: فقط «تعداد» در آن روز ثبت می‌شود و نیازی به نام مراجعه‌کننده نیست.
  • خدمات نام‌دار (ارتقا، اسمبل سیستم، نصب ویندوز و ...): هر مورد یک ردیف جدا با نام فرد.

اگر برای همان تاریخ قبلاً چیزی ثبت شده باشد، هنگام باز کردن صفحه بارگذاری و قابل
ویرایش می‌شود؛ یعنی ذخیره‌ی دوباره جایگزین همان برگه می‌شود و رکورد تکراری نمی‌سازد.
"""
from datetime import date

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTreeWidget, QTreeWidgetItem,
                               QTextEdit, QMessageBox, QGroupBox, QDateEdit, QTableWidget,
                               QTableWidgetItem, QComboBox, QHeaderView, QSplitter,
                               QAbstractItemView, QCompleter)
from PySide6.QtCore import Qt, QDate
from sqlalchemy.orm import Session

from database.models import (Task, ServiceRecord, ServiceRecordTask, Employee,
                             DEPT_IT, DEPT_SITE, DEPT_LABELS)
from ui.widgets import NoWheelSpinBox

NAMED_COLUMNS = ["خدمت", "نام فرد", "داخلی", "توضیح"]


class DailyEntryPage(QWidget):
    def __init__(self, db_session: Session, current_technician, department=DEPT_IT, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.technician = current_technician
        self.department = department
        # واحد سایت مثل قبل تیکی است؛ تعداد کنارش اختیاری است. واحد IT فقط تعدادی است.
        self.use_checkboxes = (department == DEPT_SITE)
        self.record = None            # برگه‌ی روزانه‌ی در حال ویرایش
        self.count_widgets = {}       # task_id -> QSpinBox
        self.task_items = {}          # task_id -> QTreeWidgetItem (برای تیک‌ها)
        self.named_tasks = []         # [(id, title)]
        self.setup_ui()
        self.load_data()

    # ---------------------------------------------------------------- UI
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ------- نوار بالا: تاریخ گزارش -------
        top = QHBoxLayout()
        title = QLabel(f"گزارش روزانه — {DEPT_LABELS.get(self.department, self.department)}")
        title.setObjectName("PageTitle")
        top.addWidget(title)
        top.addStretch()

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

        splitter = QSplitter(Qt.Horizontal)

        # ------- خدمات کلی -------
        if self.use_checkboxes:
            general_title = "خدمات انجام‌شده‌ی این روز (تیک بزنید — تعداد اختیاری است)"
        else:
            general_title = "خدمات کلی روز (فقط تعداد — بدون نیاز به نام)"
        general_group = QGroupBox(general_title)
        general_layout = QVBoxLayout()

        self.txt_task_search = QLineEdit()
        self.txt_task_search.setPlaceholderText("جستجوی خدمات...")
        self.txt_task_search.setClearButtonEnabled(True)
        self.txt_task_search.textChanged.connect(self._filter_tasks)
        general_layout.addWidget(self.txt_task_search)

        self.task_tree = QTreeWidget()
        self.task_tree.setColumnCount(2)
        count_header = "تعداد (اختیاری)" if self.use_checkboxes else "تعداد"
        self.task_tree.setHeaderLabels(["خدمت", count_header])
        self.task_tree.setColumnWidth(0, 340)
        self.task_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.task_tree.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.task_tree.setColumnWidth(1, 118)
        general_layout.addWidget(self.task_tree)

        btn_clear_counts = QPushButton("صفر کردن همه‌ی تعدادها")
        btn_clear_counts.setProperty("variant", "ghost")
        btn_clear_counts.setCursor(Qt.PointingHandCursor)
        btn_clear_counts.clicked.connect(self._clear_counts)
        general_layout.addWidget(btn_clear_counts)

        general_group.setLayout(general_layout)
        splitter.addWidget(general_group)

        # ------- خدمات نام‌دار (تک‌تک) -------
        named_group = QGroupBox("خدمات نیازمند نام (ارتقا / اسمبل / نصب ویندوز و ...)")
        named_layout = QVBoxLayout()

        named_bar = QHBoxLayout()
        btn_add_row = QPushButton("+ افزودن مورد")
        btn_add_row.setCursor(Qt.PointingHandCursor)
        btn_add_row.clicked.connect(lambda: self.add_named_row())

        btn_del_row = QPushButton("حذف ردیف انتخاب‌شده")
        btn_del_row.setProperty("variant", "danger")
        btn_del_row.setCursor(Qt.PointingHandCursor)
        btn_del_row.clicked.connect(self.remove_named_row)

        named_bar.addWidget(btn_add_row)
        named_bar.addWidget(btn_del_row)
        named_bar.addStretch()
        named_layout.addLayout(named_bar)

        self.named_table = QTableWidget()
        self.named_table.setColumnCount(len(NAMED_COLUMNS))
        self.named_table.setHorizontalHeaderLabels(NAMED_COLUMNS)
        self.named_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.named_table.verticalHeader().setVisible(False)
        # ارتفاع ردیف‌ها را بالا می‌بریم تا کمبو/ورودی‌ها بریده نشوند و متن دیده شود
        self.named_table.verticalHeader().setDefaultSectionSize(44)
        header = self.named_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # خدمت
        header.setSectionResizeMode(1, QHeaderView.Stretch)           # نام فرد
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # داخلی
        header.setSectionResizeMode(3, QHeaderView.Stretch)           # توضیح
        named_layout.addWidget(self.named_table)

        self.lbl_named_hint = QLabel("")
        self.lbl_named_hint.setObjectName("Muted")
        self.lbl_named_hint.setWordWrap(True)
        named_layout.addWidget(self.lbl_named_hint)

        named_group.setLayout(named_layout)
        splitter.addWidget(named_group)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

        # ------- توضیح روز و ذخیره -------
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("توضیح کلی این روز (اختیاری)...")
        self.txt_notes.setMaximumHeight(70)
        layout.addWidget(self.txt_notes)

        bottom = QHBoxLayout()
        btn_submit = QPushButton("ذخیره‌ی گزارش روز")
        btn_submit.setProperty("variant", "success")
        btn_submit.setMinimumHeight(42)
        btn_submit.setCursor(Qt.PointingHandCursor)
        btn_submit.clicked.connect(self.save_record)

        btn_delete = QPushButton("حذف گزارش این روز")
        btn_delete.setProperty("variant", "danger")
        btn_delete.setMinimumHeight(42)
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self.delete_record)

        bottom.addWidget(btn_submit, 3)
        bottom.addWidget(btn_delete, 1)
        layout.addLayout(bottom)

    # ------------------------------------------------------------ داده‌ها
    def selected_date(self):
        return self.date_edit.date().toPython()

    def load_data(self):
        """درخت خدمات و ردیف‌های نام‌دارِ همان تاریخ را بارگذاری می‌کند."""
        self._build_task_tree()
        self._load_employee_completer()
        self._load_existing_record()

    def _active_tasks(self):
        return (self.db.query(Task)
                .filter(Task.is_active.is_(True), Task.department == self.department)
                .order_by(Task.position, Task.id)
                .all())

    @staticmethod
    def _ordered_children(parent_task):
        active = [s for s in parent_task.sub_tasks if s.is_active]
        return sorted(active, key=lambda t: ((t.position or 0), t.id))

    def _build_task_tree(self):
        self.task_tree.clear()
        self.count_widgets = {}
        self.task_items = {}
        self.named_tasks = []

        roots = [t for t in self._active_tasks() if t.parent_task_id is None]
        for task in roots:
            if task.requires_name:
                continue  # خدمات نام‌دار در جدول سمت دیگر ثبت می‌شوند
            item = QTreeWidgetItem(self.task_tree, [task.title, ""])
            item.setData(0, Qt.UserRole, task.id)
            self._attach_spin(item, task)          # سردسته‌ها هم قابل شمارش‌اند
            self._add_branch(item, task)
        self.task_tree.expandAll()

        self._refresh_named_task_list()

    def _add_branch(self, parent_item, parent_task):
        for sub in self._ordered_children(parent_task):
            if sub.requires_name:
                # خدمات نام‌دار در جدول سمت دیگر ثبت می‌شوند، نه در درخت شمارش
                continue
            item = QTreeWidgetItem(parent_item, [sub.title, ""])
            item.setData(0, Qt.UserRole, sub.id)
            self._attach_spin(item, sub)           # هر خدمت (سردسته یا زیرمجموعه) تعداد دارد
            self._add_branch(item, sub)

    def _attach_spin(self, item, task):
        # در واحد سایت هر مورد یک تیک هم دارد (مثل قبل)
        if self.use_checkboxes:
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Unchecked)

        spin = NoWheelSpinBox()
        spin.setRange(0, 999)
        spin.setValue(0)
        spin.setAlignment(Qt.AlignCenter)
        spin.setFixedSize(104, 34)
        self.task_tree.setItemWidget(item, 1, spin)
        # ارتفاع ردیف را به‌اندازه‌ی اسپین‌باکس بزرگ می‌کنیم تا محتوا بریده نشود
        item.setSizeHint(1, spin.sizeHint())
        self.count_widgets[task.id] = spin
        self.task_items[task.id] = item

    def _refresh_named_task_list(self):
        # ترتیب بر اساس اولویت (position) که از _active_tasks می‌آید
        self.named_tasks = [(t.id, self._full_title(t))
                            for t in self._active_tasks() if t.requires_name]
        if self.named_tasks:
            self.lbl_named_hint.setText(
                "این خدمات در «مدیریت خدمات» با گزینه‌ی «نیاز به نام فرد» علامت خورده‌اند.")
        else:
            self.lbl_named_hint.setText(
                "هنوز خدمتی با گزینه‌ی «نیاز به نام فرد» تعریف نشده است. "
                "در تب «مدیریت خدمات» موارد ارتقا / اسمبل / نصب ویندوز را علامت بزنید.")

    def _full_title(self, task):
        parts = [task.title]
        parent = task.parent
        guard = 0
        while parent is not None and guard < 10:
            parts.append(parent.title)
            parent = parent.parent
            guard += 1
        return " ← ".join(reversed(parts))

    def _load_employee_completer(self):
        names = [e.full_name for e in self.db.query(Employee).filter_by(is_active=True).all()]
        self._employee_names = names

    # --------------------------------------------------- بارگذاری برگه‌ی روز
    def find_record(self, day):
        return (self.db.query(ServiceRecord)
                .filter(ServiceRecord.technician_id == self.technician.id,
                        ServiceRecord.department == self.department,
                        ServiceRecord.report_date == day)
                .first())

    def _load_existing_record(self):
        day = self.selected_date()
        self.record = self.find_record(day)

        self._clear_counts()
        self.named_table.setRowCount(0)
        self.txt_notes.clear()

        if not self.record:
            self.lbl_state.setText("برای این تاریخ هنوز گزارشی ثبت نشده است — یک برگه‌ی جدید.")
            return

        self.lbl_state.setText(
            f"گزارش ثبت‌شده‌ی این روز (کد #{self.record.id}) بارگذاری شد؛ "
            "می‌توانید ویرایش کنید و دوباره ذخیره بزنید.")
        self.txt_notes.setPlainText(self.record.short_description or "")

        for line in self.record.tasks:
            if line.person_name:
                self.add_named_row(task_id=line.task_id, name=line.person_name,
                                   ext=line.person_extension, note=line.note)
                continue
            spin = self.count_widgets.get(line.task_id)
            item = self.task_items.get(line.task_id)
            qty = line.quantity or 1
            if self.use_checkboxes and item is not None:
                item.setCheckState(0, Qt.Checked)
                # عدد فقط وقتی بیشتر از ۱ باشد نشان داده می‌شود؛ در غیر این صورت خالی می‌ماند
                if spin:
                    spin.setValue(qty if qty > 1 else 0)
            elif spin:
                spin.setValue(qty)

    def _clear_counts(self):
        for spin in self.count_widgets.values():
            spin.setValue(0)
        for item in self.task_items.values():
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(0, Qt.Unchecked)

    # ------------------------------------------------------ جدول نام‌دارها
    def add_named_row(self, task_id=None, name="", ext="", note=""):
        if not self.named_tasks:
            QMessageBox.information(
                self, "توجه",
                "ابتدا در تب «مدیریت خدمات» حداقل یک خدمت را «نیازمند نام» تعریف کنید.")
            return
        row = self.named_table.rowCount()
        self.named_table.insertRow(row)

        cmb = QComboBox()
        for tid, label in self.named_tasks:
            cmb.addItem(label, tid)
        if task_id is not None:
            idx = cmb.findData(task_id)
            if idx >= 0:
                cmb.setCurrentIndex(idx)
        self.named_table.setCellWidget(row, 0, cmb)

        txt_name = QLineEdit(name or "")
        txt_name.setPlaceholderText("نام فرد...")
        completer = QCompleter(getattr(self, "_employee_names", []))
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        txt_name.setCompleter(completer)
        self.named_table.setCellWidget(row, 1, txt_name)

        ext_edit = QLineEdit(ext or ""); ext_edit.setPlaceholderText("داخلی...")
        self.named_table.setCellWidget(row, 2, ext_edit)
        note_edit = QLineEdit(note or ""); note_edit.setPlaceholderText("توضیح (اختیاری)...")
        self.named_table.setCellWidget(row, 3, note_edit)

        self.named_table.setCurrentCell(row, 1)
        return row

    def remove_named_row(self):
        row = self.named_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "توجه", "ابتدا یک ردیف را انتخاب کنید.")
            return
        self.named_table.removeRow(row)

    def _named_rows(self):
        rows = []
        for row in range(self.named_table.rowCount()):
            cmb = self.named_table.cellWidget(row, 0)
            name = self.named_table.cellWidget(row, 1).text().strip()
            ext = self.named_table.cellWidget(row, 2).text().strip()
            note = self.named_table.cellWidget(row, 3).text().strip()
            rows.append({"row": row + 1, "task_id": cmb.currentData(),
                         "name": name, "ext": ext, "note": note})
        return rows

    # --------------------------------------------------------------- فیلتر
    def _filter_tasks(self, text):
        query = (text or "").strip().lower()

        def apply(item):
            self_match = query in item.text(0).lower()
            child_match = False
            for i in range(item.childCount()):
                if apply(item.child(i)):
                    child_match = True
            visible = self_match or child_match or not query
            item.setHidden(not visible)
            if query and child_match:
                item.setExpanded(True)
            return visible

        for i in range(self.task_tree.topLevelItemCount()):
            apply(self.task_tree.topLevelItem(i))

    def _collect_counts(self):
        """{task_id: quantity} برای خطوط شمارشی.

        واحد سایت: هر موردِ تیک‌خورده حساب می‌شود (تعداد اگر خالی باشد = ۱).
        واحد IT: هر موردی که تعدادش بیشتر از صفر باشد.
        """
        counts = {}
        for tid, spin in self.count_widgets.items():
            val = spin.value()
            if self.use_checkboxes:
                item = self.task_items.get(tid)
                checked = item is not None and item.checkState(0) == Qt.Checked
                if checked or val > 0:
                    counts[tid] = val if val > 0 else 1
            elif val > 0:
                counts[tid] = val
        return counts

    # --------------------------------------------------------------- ذخیره
    def save_record(self):
        day = self.selected_date()
        counts = self._collect_counts()
        named = self._named_rows()

        for item in named:
            if not item["name"]:
                QMessageBox.warning(
                    self, "خطا",
                    f"ردیف {item['row']} از خدمات نام‌دار بدون نام است. "
                    "برای این خدمات وارد کردن نام فرد الزامی است.")
                return

        if not counts and not named:
            QMessageBox.warning(self, "خطا",
                                "حداقل یک خدمت با تعداد، یا یک مورد نام‌دار وارد کنید.")
            return

        record = self.record or self.find_record(day)
        if record is None:
            record = ServiceRecord(
                technician_id=self.technician.id,
                # برگه‌ی روزانه مراجعه‌کننده‌ی واحد ندارد؛ رکورد پیش‌فرض فقط برای
                # سازگاری با دیتابیس‌های قدیمی است که این ستون را اجباری ساخته‌اند
                requester_employee_id=self._placeholder_employee_id(),
                technician_name_snapshot=self.technician.full_name,
                department=self.department,
                report_date=day,
            )
            self.db.add(record)
            self.db.flush()
        else:
            record.technician_name_snapshot = self.technician.full_name
            record.department = self.department
            record.report_date = day
            for line in list(record.tasks):
                self.db.delete(line)
            self.db.flush()

        record.short_description = self.txt_notes.toPlainText().strip()

        for task_id, qty in counts.items():
            self.db.add(ServiceRecordTask(
                service_record_id=record.id, task_id=task_id, quantity=qty))

        for item in named:
            self._ensure_employee(item["name"], item["ext"])
            self.db.add(ServiceRecordTask(
                service_record_id=record.id,
                task_id=item["task_id"],
                quantity=1,
                person_name=item["name"],
                person_extension=item["ext"],
                note=item["note"],
            ))

        self.db.commit()
        total = sum(counts.values()) + len(named)
        QMessageBox.information(
            self, "موفق",
            f"گزارش {day.strftime('%Y/%m/%d')} ذخیره شد. مجموع خدمات ثبت‌شده: {total}")
        self.load_data()

    def _placeholder_employee_id(self):
        emp = self.db.query(Employee).filter_by(full_name="—").first()
        if not emp:
            emp = Employee(full_name="—", internal_extension="", is_active=False)
            self.db.add(emp)
            self.db.flush()
        return emp.id

    def _ensure_employee(self, name, ext):
        """نام افراد را برای تکمیل خودکار دفعات بعد نگه می‌دارد."""
        if not name:
            return
        emp = self.db.query(Employee).filter_by(full_name=name).first()
        if not emp:
            self.db.add(Employee(full_name=name, internal_extension=ext or ""))
            self.db.flush()
        elif ext and not emp.internal_extension:
            emp.internal_extension = ext

    def delete_record(self):
        day = self.selected_date()
        record = self.record or self.find_record(day)
        if not record:
            QMessageBox.information(self, "توجه", "برای این تاریخ گزارشی ثبت نشده است.")
            return
        confirm = QMessageBox.question(
            self, "تأیید حذف",
            f"کل گزارش تاریخ {day.strftime('%Y/%m/%d')} حذف شود؟ این عملیات قابل بازگشت نیست.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        for line in list(record.tasks):
            self.db.delete(line)
        self.db.delete(record)
        self.db.commit()
        self.record = None
        self.load_data()

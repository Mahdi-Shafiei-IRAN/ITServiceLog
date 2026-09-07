from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
                               QTextEdit, QMessageBox, QGroupBox, QCompleter, QInputDialog)
from PySide6.QtCore import Qt
from sqlalchemy import func
from sqlalchemy.orm import Session
from database.models import Employee, Task, ServiceRecord, ServiceRecordTask, SystemDevice
from services.remote_detector import detect_sessions, format_system_label

class ServiceRecordPage(QWidget):
    def __init__(self, db_session: Session, current_technician):
        super().__init__()
        self.db = db_session
        self.technician = current_technician
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # بخش مراجعه‌کننده (فقط فیلدهای متنی آزاد)
        req_group = QGroupBox("مراجعه‌کننده (نام فرد را تایپ کنید)")
        req_layout = QHBoxLayout()
        
        self.txt_req_name = QLineEdit()
        self.txt_req_name.setPlaceholderText("نام شخص (مثلاً: احمد محمدی)...")
        
        self.txt_req_ext = QLineEdit()
        self.txt_req_ext.setPlaceholderText("شماره داخلی...")
        
        self.txt_system = QLineEdit()
        self.txt_system.setPlaceholderText("نام سیستم / IP...")

        # دکمهٔ دریافت خودکار نام/IP از نرم‌افزار ریموت (DameWare)
        self.btn_detect = QPushButton("دریافت از ریموت 🔄")
        self.btn_detect.setToolTip("خواندن خودکار نام سیستم و IP از پنجرهٔ باز DameWare")
        self.btn_detect.setStyleSheet(
            "background-color: #2563EB; color: white; padding: 6px 10px; "
            "border-radius: 4px; font-weight: bold;")
        self.btn_detect.clicked.connect(lambda: self.detect_remote(silent=False))

        req_layout.addWidget(QLabel("نام:"))
        req_layout.addWidget(self.txt_req_name, stretch=2)
        req_layout.addWidget(QLabel("داخلی:"))
        req_layout.addWidget(self.txt_req_ext, stretch=1)
        req_layout.addWidget(QLabel("سیستم:"))
        req_layout.addWidget(self.txt_system, stretch=1)
        req_layout.addWidget(self.btn_detect)
        req_group.setLayout(req_layout)
        layout.addWidget(req_group)

        # درخت کارها
        task_group = QGroupBox("عملیات انجام‌شده")
        task_layout = QVBoxLayout()

        # جعبه جستجو برای فیلتر کردن گزینه‌های درخت
        self.txt_task_search = QLineEdit()
        self.txt_task_search.setPlaceholderText("جستجوی گزینه‌ها...")
        self.txt_task_search.setClearButtonEnabled(True)
        self.txt_task_search.textChanged.connect(self._filter_tasks)
        task_layout.addWidget(self.txt_task_search)

        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderHidden(True)
        task_layout.addWidget(self.task_tree)
        task_group.setLayout(task_layout)
        layout.addWidget(task_group, stretch=1)

        # توضیحات و ثبت
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("توضیح کوتاه (اختیاری)...")
        self.txt_notes.setMaximumHeight(80)
        layout.addWidget(self.txt_notes)

        btn_submit = QPushButton("ثبت گزارش")
        btn_submit.setProperty("variant", "success")
        btn_submit.setMinimumHeight(42)
        btn_submit.setCursor(Qt.PointingHandCursor)
        btn_submit.clicked.connect(self.save_record)
        layout.addWidget(btn_submit)

    def load_data(self):
        """این تابع درخت کارها و لیست تکمیل خودکار نام‌ها را رفرش می‌کند"""
        # پر کردن درخت کارها
        self.task_tree.clear()
        top_tasks = self.db.query(Task).filter_by(parent_task_id=None, is_active=True).all()
        for task in top_tasks:
            parent_item = QTreeWidgetItem(self.task_tree, [task.title])
            parent_item.setData(0, Qt.UserRole, task.id)
            parent_item.setFlags(parent_item.flags() | Qt.ItemIsUserCheckable)
            parent_item.setCheckState(0, Qt.Unchecked)
            self._add_sub_tasks(parent_item, task)
        self.task_tree.expandAll()

        # پیشنهاد خودکار نام‌ها (Auto-complete)
        employees = self.db.query(Employee).filter_by(is_active=True).all()
        names = [emp.full_name for emp in employees]
        completer = QCompleter(names)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.txt_req_name.setCompleter(completer)

        # تلاش بی‌صدا برای پرکردن خودکار سیستم/IP از ریموت هنگام باز شدن صفحه
        self.detect_remote(silent=True)

    # ------------------ تشخیص خودکار از نرم‌افزار ریموت ------------------
    def detect_remote(self, silent=True):
        """
        نام/IP دستگاه متصل را از پنجرهٔ DameWare می‌خواند و فیلد سیستم را پر می‌کند.
        silent=True یعنی حالت خودکار (بدون پیام خطا و بدون بازنویسی فیلدهای پرشده).
        """
        try:
            sessions = detect_sessions(resolve=not silent)
        except Exception:
            sessions = []

        if not sessions:
            if not silent:
                titles = "\n".join(self._debug_titles()) or "(هیچ پنجره‌ای یافت نشد)"
                QMessageBox.information(
                    self, "ریموت یافت نشد",
                    "پنجرهٔ فعال DameWare پیدا نشد.\n"
                    "اگر به سیستمی متصل هستید، عنوان پنجره‌های باز این‌هاست؛\n"
                    "در صورت نیاز فایل remote_config.json را تنظیم کنید:\n\n" + titles)
            return

        # اگر چند نشست باز است، در حالت دستی از کاربر می‌پرسیم
        session = sessions[0]
        if len(sessions) > 1 and not silent:
            labels = [format_system_label(s["name"], s["ip"]) or s["title"] for s in sessions]
            choice, ok = QInputDialog.getItem(
                self, "انتخاب سیستم",
                "چند اتصال DameWare باز است. کدام؟", labels, 0, False)
            if not ok:
                return
            session = sessions[labels.index(choice)]

        self._apply_detected_host(session["name"], session["ip"], silent=silent)

    def _apply_detected_host(self, name, ip, silent=True):
        """فیلد سیستم را پر می‌کند و در صورت وجود نگاشت، نام/داخلی را هم می‌آورد."""
        label = format_system_label(name, ip)
        if not label:
            return
        # فیلد سیستم را فقط اگر خالی است (حالت خودکار) یا همیشه (حالت دستی) پر کن
        if not silent or not self.txt_system.text().strip():
            self.txt_system.setText(label)

        matched = self._lookup_mapping(name, ip)
        if matched:
            emp = matched
            if emp.internal_extension and (not silent or not self.txt_req_ext.text().strip()):
                self.txt_req_ext.setText(emp.internal_extension)
            if emp.full_name and (not silent or not self.txt_req_name.text().strip()):
                self.txt_req_name.setText(emp.full_name)

        if not silent:
            extra = ""
            if matched:
                extra = f"\nکارمند: {matched.full_name} | داخلی: {matched.internal_extension or '-'}"
            QMessageBox.information(self, "دریافت شد", f"سیستم: {label}{extra}")

    def _lookup_mapping(self, name, ip):
        """
        از نام/IP سیستم، کارمندِ متناظر را در دیتابیس پیدا می‌کند.
        سیستم → کارمند → داخلی (بر اساس جدول‌های SystemDevice و Employee).
        """
        try:
            device = None
            if name:
                device = (self.db.query(SystemDevice)
                          .filter(func.lower(SystemDevice.system_name) == name.lower())
                          .first())
            if not device and ip:
                device = (self.db.query(SystemDevice)
                          .filter(SystemDevice.ip_address == ip).first())
            if not device:
                return None
            return (self.db.query(Employee)
                    .filter_by(system_id=device.id, is_active=True).first())
        except Exception:
            return None

    def _debug_titles(self):
        """برای تشخیص عیب: عنوان پنجره‌هایی که شامل کلمات کلیدی رایج‌اند."""
        try:
            from services.remote_detector import list_window_titles
            keys = ("remote", "dame", "control", "mrc", "support")
            return [t for t in list_window_titles() if any(k in t.lower() for k in keys)][:15]
        except Exception:
            return []

    def _add_sub_tasks(self, parent_item, parent_task):
        for sub_task in parent_task.sub_tasks:
            if not sub_task.is_active: continue
            child = QTreeWidgetItem(parent_item, [sub_task.title])
            child.setData(0, Qt.UserRole, sub_task.id)
            child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
            child.setCheckState(0, Qt.Unchecked)
            self._add_sub_tasks(child, sub_task)

    def _filter_tasks(self, text):
        """فیلتر کردن درخت گزینه‌ها بر اساس متن جستجو.

        هر آیتمی که خودش یا یکی از فرزندانش با متن هم‌خوانی داشته باشد نمایش داده
        می‌شود؛ بقیه پنهان می‌شوند. با خالی‌بودن جستجو همه‌چیز دوباره نمایش داده می‌شود.
        """
        query = (text or "").strip().lower()

        def apply(item):
            # آیا این آیتم خودش هم‌خوانی دارد؟
            self_match = query in item.text(0).lower()
            # آیا یکی از فرزندان هم‌خوانی دارد؟ (به‌صورت بازگشتی)
            child_match = False
            for i in range(item.childCount()):
                if apply(item.child(i)):
                    child_match = True
            visible = self_match or child_match or not query
            item.setHidden(not visible)
            # وقتی به خاطر جستجو چیزی پیدا شد، شاخه را باز کن تا دیده شود
            if query and child_match:
                item.setExpanded(True)
            return visible

        for i in range(self.task_tree.topLevelItemCount()):
            apply(self.task_tree.topLevelItem(i))

    def get_checked_tasks(self, root=None, checked=None):
        if checked is None: checked = []
        iterator = range(self.task_tree.topLevelItemCount()) if root is None else range(root.childCount())
        for i in iterator:
            item = self.task_tree.topLevelItem(i) if root is None else root.child(i)
            if item.checkState(0) == Qt.Checked:
                checked.append(item.data(0, Qt.UserRole))
            self.get_checked_tasks(item, checked)
        return checked

    def save_record(self):
        name = self.txt_req_name.text().strip()
        tasks = self.get_checked_tasks()

        # نام اختیاری است؛ فقط انتخاب حداقل یک عملیات الزامی است.
        if not tasks:
            QMessageBox.warning(self, "خطا", "انتخاب حداقل یک عملیات الزامی است.")
            return

        # اگر نام وارد شده باشد، کارمند را پیدا/ایجاد می‌کنیم؛ در غیر این صورت
        # از یک کارمند پیش‌فرض «نامشخص» استفاده می‌کنیم تا نام اختیاری بماند.
        if name:
            employee = self.db.query(Employee).filter_by(full_name=name).first()
            if not employee:
                employee = Employee(full_name=name, internal_extension=self.txt_req_ext.text().strip())
                self.db.add(employee)
                self.db.flush()
            requester_name = employee.full_name
        else:
            employee = self.db.query(Employee).filter_by(full_name="نامشخص").first()
            if not employee:
                employee = Employee(full_name="نامشخص", internal_extension="")
                self.db.add(employee)
                self.db.flush()
            requester_name = ""  # در گزارش‌ها خالی نمایش داده می‌شود

        record = ServiceRecord(
            technician_id=self.technician.id,
            requester_employee_id=employee.id,
            technician_name_snapshot=self.technician.full_name,
            requester_name_snapshot=requester_name,
            requester_extension_snapshot=self.txt_req_ext.text().strip(),
            system_name_snapshot=self.txt_system.text().strip(),
            short_description=self.txt_notes.toPlainText()
        )
        self.db.add(record)
        
        # کلید حل مشکل ثبت نشدن تیک‌ها این دستور است!
        self.db.flush() 
        
        for task_id in tasks:
            self.db.add(ServiceRecordTask(service_record_id=record.id, task_id=task_id))
            
        self.db.commit()
        QMessageBox.information(self, "موفق", "گزارش شما سریعاً ثبت شد.")
        
        self.txt_req_name.clear(); self.txt_req_ext.clear()
        self.txt_system.clear(); self.txt_notes.clear()
        self.load_data()
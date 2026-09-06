from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
                               QTextEdit, QMessageBox, QGroupBox, QCompleter, QInputDialog,
                               QFrame)
from PySide6.QtCore import Qt
from sqlalchemy import func
from sqlalchemy.orm import Session
from database.models import Employee, Task, ServiceRecord, ServiceRecordTask, SystemDevice
from services.remote_detector import (detect_sessions, format_system_label,
                                       derive_person_name, is_remote_connected,
                                       get_window_rect, is_offscreen_rect)
from services import task_inference, session_ocr
from services.debug_log import log as ai_log

class ServiceRecordPage(QWidget):
    def __init__(self, db_session: Session, current_technician):
        super().__init__()
        self.db = db_session
        self.technician = current_technician
        self.watcher = None
        self.setup_ui()
        self.load_data()
        self._init_watcher()

    def _init_watcher(self):
        """ناظرِ جلسهٔ ریموت را روی یک نخِ جدا راه می‌اندازد (در صورت خطا بی‌اثر).
        توقفِ نخ توسطِ MainWindow.closeEvent انجام می‌شود (هم خروج و هم Logout)."""
        try:
            from services.session_watcher import SessionWatcher
            self.watcher = SessionWatcher(self)
            self.watcher.session_ended.connect(self._on_session_ended)
            self.watcher.start()
        except Exception:
            self.watcher = None

    def stop_watcher(self):
        """توقفِ ایمنِ نخِ ناظر (از سمتِ MainWindow هنگام بسته‌شدن صدا زده می‌شود)."""
        try:
            if self.watcher is not None:
                self.watcher.stop()
        except Exception:
            pass

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # اگر نام سیستم پر شود، نام شخص به‌طور خودکار از روی آن حدس زده می‌شود؛
        # این متغیر آخرین نامِ حدس‌زده‌شده را نگه می‌دارد تا نامِ دستیِ کاربر بازنویسی نشود.
        self._last_derived = ""
        # پیشنهادِ خودکارِ در انتظار (توضیح + موارد) از آخرین جلسهٔ ریموت
        self._pending_suggestion = None

        # بنر پیشنهادِ خودکار (پیش‌فرض پنهان است؛ پس از پایانِ جلسهٔ ریموت ظاهر می‌شود)
        self.ai_banner = QFrame()
        self.ai_banner.setStyleSheet(
            "QFrame { background-color: #ECFDF5; border: 1px solid #34D399; border-radius: 6px; }")
        ai_row = QHBoxLayout(self.ai_banner)
        ai_row.setContentsMargins(10, 6, 10, 6)
        self.ai_lbl = QLabel("")
        self.ai_lbl.setWordWrap(True)
        self.ai_lbl.setStyleSheet("border: none; background: transparent;")
        btn_ai_dismiss = QPushButton("نادیده بگیر")
        btn_ai_dismiss.setCursor(Qt.PointingHandCursor)
        btn_ai_dismiss.clicked.connect(self._clear_suggestion)
        ai_row.addWidget(self.ai_lbl, stretch=1)
        ai_row.addWidget(btn_ai_dismiss)
        self.ai_banner.setVisible(False)
        layout.addWidget(self.ai_banner)

        # بخش مراجعه‌کننده (فقط فیلدهای متنی آزاد)
        req_group = QGroupBox("مراجعه‌کننده (با پر شدن نام سیستم، نام فرد خودکار پر می‌شود)")
        req_layout = QHBoxLayout()

        self.txt_req_name = QLineEdit()
        self.txt_req_name.setPlaceholderText("نام شخص (اختیاری اگر سیستم پر باشد)...")

        self.txt_req_ext = QLineEdit()
        self.txt_req_ext.setPlaceholderText("شماره داخلی...")

        self.txt_system = QLineEdit()
        self.txt_system.setPlaceholderText("نام سیستم / IP (مثلاً it-sadeghi)...")
        # با هر تغییر در نام سیستم، نام شخص را خودکار حدس بزن
        self.txt_system.textChanged.connect(self._on_system_changed)

        # دکمهٔ دریافت خودکار نام/IP از نرم‌افزار ریموت (DameWare)
        self.btn_detect = QPushButton("دریافت از ریموت 🔄")
        self.btn_detect.setToolTip("خواندن خودکار نام سیستم و IP از پنجرهٔ باز DameWare")
        self.btn_detect.setStyleSheet(
            "background-color: #2563EB; color: white; padding: 6px 10px; "
            "border-radius: 4px; font-weight: bold;")
        self.btn_detect.clicked.connect(lambda: self.detect_remote(silent=False))

        # دکمهٔ اجرای دستیِ دستیارِ خودکار: همین حالا از صفحهٔ ریموت OCR بگیر و پیشنهاد بده
        self.btn_suggest = QPushButton("پیشنهاد از جلسهٔ فعلی 🤖")
        self.btn_suggest.setToolTip("گرفتنِ فوریِ متنِ صفحهٔ ریموت و تشخیصِ خودکارِ توضیح و موارد")
        self.btn_suggest.setCursor(Qt.PointingHandCursor)
        self.btn_suggest.clicked.connect(self._manual_suggest)

        req_layout.addWidget(QLabel("نام:"))
        req_layout.addWidget(self.txt_req_name, stretch=2)
        req_layout.addWidget(QLabel("داخلی:"))
        req_layout.addWidget(self.txt_req_ext, stretch=1)
        req_layout.addWidget(QLabel("سیستم:"))
        req_layout.addWidget(self.txt_system, stretch=1)
        req_layout.addWidget(self.btn_detect)
        req_layout.addWidget(self.btn_suggest)
        req_group.setLayout(req_layout)
        layout.addWidget(req_group)

        # درخت کارها
        task_group = QGroupBox("عملیات انجام‌شده")
        task_layout = QVBoxLayout()

        # جستجو در موارد (وقتی تعداد موارد زیاد شود کمک می‌کند)
        self.txt_task_search = QLineEdit()
        self.txt_task_search.setPlaceholderText("جستجو در موارد... 🔍")
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
        self.txt_notes.setPlaceholderText("توضیح کوتاه (اگر خالی بماند، خودکار از روی موارد تیک‌خورده ساخته می‌شود)...")
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

        # اگر پیشنهادِ خودکاری در انتظار است، تیک‌هایش را روی درختِ تازه‌ساخته دوباره اعمال کن
        if getattr(self, "_pending_suggestion", None):
            self._check_task_ids(set(self._pending_suggestion["result"]["task_ids"]))

    # ------------------ حدس نام شخص از روی نام سیستم ------------------
    def _name_is_auto(self):
        """آیا محتوای فعلیِ فیلد نام، خالی یا همان مقدار حدس‌زده‌شده است؟"""
        current = self.txt_req_name.text().strip()
        return not current or current == self._last_derived

    def _on_system_changed(self, text):
        """با تغییر نام سیستم، اگر کاربر نامی دستی وارد نکرده باشد، نام را حدس بزن."""
        if not self._name_is_auto():
            return  # کاربر نام را دستی وارد کرده؛ دست نمی‌زنیم
        derived = derive_person_name(text)
        self._last_derived = derived
        # جلوگیری از حلقهٔ سیگنال: فقط در صورت تفاوت، مقدار را ست کن
        if self.txt_req_name.text() != derived:
            self.txt_req_name.setText(derived)

    # ------------------ جستجو در موارد ------------------
    @staticmethod
    def _norm(s):
        """یکسان‌سازی حروف عربی/فارسی برای جستجوی بهتر."""
        return (s or "").replace("ي", "ی").replace("ك", "ک").strip().lower()

    def _filter_tasks(self, text):
        """موارد درخت را بر اساس متن جستجو فیلتر می‌کند (شاخهٔ والدِ مورد یافته‌شده باز می‌ماند)."""
        query = self._norm(text)
        for i in range(self.task_tree.topLevelItemCount()):
            self._filter_item(self.task_tree.topLevelItem(i), query)
        if not query:
            self.task_tree.expandAll()

    def _filter_item(self, item, query):
        """بازگشتی: مورد را در صورت تطابقِ خود یا یکی از زیرمواردش نمایش می‌دهد."""
        self_match = query in self._norm(item.text(0))
        child_match = False
        for i in range(item.childCount()):
            if self._filter_item(item.child(i), query):
                child_match = True
        visible = self_match or child_match
        item.setHidden(not visible)
        if child_match:
            item.setExpanded(True)
        return visible

    # ------------------ پیشنهادِ خودکار از جلسهٔ ریموت (OCR) ------------------
    def _on_session_ended(self, evidence, info):
        """با پایانِ جلسهٔ ریموت، از روی شواهدِ OCR توضیح و موارد را پیشنهاد می‌کند."""
        try:
            tasks = [(t.id, t.title) for t in
                     self.db.query(Task).filter_by(is_active=True).all()]
            result = task_inference.infer(evidence, tasks)
        except Exception:
            return
        if not result["task_ids"] and not result["description"]:
            return
        self._pending_suggestion = {"result": result, "info": info}
        self._apply_suggestion()

    def _apply_suggestion(self):
        """پیشنهادِ در انتظار را روی فرم اعمال می‌کند (فقط فیلدهای خالی را پر می‌کند)."""
        sug = self._pending_suggestion
        if not sug:
            return
        result, info = sug["result"], sug["info"]
        label = info.get("label") or ""
        if label and not self.txt_system.text().strip():
            self.txt_system.setText(label)  # نام شخص هم از روی همین حدس زده می‌شود
        if result["description"] and not self.txt_notes.toPlainText().strip():
            self.txt_notes.setPlainText(result["description"])
        self._check_task_ids(set(result["task_ids"]))
        n = len(result["task_ids"])
        self.ai_lbl.setText(
            "🤖 پیشنهاد خودکار از جلسهٔ اخیر"
            + (f" ({label})" if label else "")
            + f": {n} مورد تیک خورد و توضیح پیش‌نویس شد. لطفاً بررسی و «ثبت گزارش» کنید.")
        self.ai_banner.setVisible(True)

    def _check_task_ids(self, ids, root=None):
        """موارد با شناسه‌های داده‌شده را تیک می‌زند و شاخهٔ والدشان را باز می‌کند."""
        if not ids:
            return
        count = self.task_tree.topLevelItemCount() if root is None else root.childCount()
        for i in range(count):
            item = self.task_tree.topLevelItem(i) if root is None else root.child(i)
            if item.data(0, Qt.UserRole) in ids:
                item.setCheckState(0, Qt.Checked)
                p = item.parent()
                while p is not None:
                    p.setExpanded(True)
                    p = p.parent()
            self._check_task_ids(ids, item)

    def _clear_suggestion(self):
        """بنر پیشنهاد را می‌بندد (تیک‌ها و متن‌های اعمال‌شده دست‌نخورده می‌مانند)."""
        self._pending_suggestion = None
        if self.ai_banner is not None:
            self.ai_banner.setVisible(False)

    def _manual_suggest(self):
        """اجرای دستیِ دستیار: OCRِ فوری از پنجرهٔ ریموت + شواهدِ جمع‌شده → پیشنهاد."""
        from PySide6.QtWidgets import QApplication
        ai_log("manual: کاربر «پیشنهاد از جلسهٔ فعلی» را زد")
        evidence = ""
        name = ip = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            hwnd = name = ip = None
            accumulated = ""
            if self.watcher is not None:
                hwnd, name, ip = self.watcher.current_target()
                accumulated = self.watcher.current_evidence()
            else:
                sessions = detect_sessions(resolve=False)
                if sessions:
                    hwnd = sessions[0].get("hwnd")
                    name, ip = sessions[0].get("name"), sessions[0].get("ip")

            # یک عکسِ فوری از پنجرهٔ ریموتِ فعلی (اگر پنجرهٔ مناسبی پیدا شد)
            one_shot = ""
            rect = get_window_rect(hwnd) if hwnd else None
            if rect and not is_offscreen_rect(rect):
                one_shot = session_ocr.capture_and_ocr(rect)
            evidence = (accumulated + "\n" + one_shot).strip()
            ai_log(f"manual: hwnd={hwnd} rect={rect} accumulated_chars={len(accumulated)} "
                   f"oneshot_chars={len(one_shot)}")
        finally:
            QApplication.restoreOverrideCursor()

        if not evidence:
            QMessageBox.information(
                self, "چیزی یافت نشد",
                "متنی از صفحهٔ ریموت خوانده نشد.\n"
                "• مطمئن شوید پنجرهٔ DameWare باز و جلوی صفحه است.\n"
                f"• جزئیات در فایل لاگ:\n{self._ai_log_path()}")
            return

        info = {"name": name, "ip": ip, "label": format_system_label(name, ip)}
        self._on_session_ended(evidence, info)
        if not self._pending_suggestion:
            QMessageBox.information(
                self, "موردی تشخیص داده نشد",
                "متن خوانده شد ولی با هیچ موردی تطبیق نداشت.\n"
                "می‌توانید قوانینِ کلیدواژه را در فایلِ تنظیمات کامل‌تر کنید.\n"
                f"لاگ:\n{self._ai_log_path()}")

    @staticmethod
    def _ai_log_path():
        try:
            from services.debug_log import log_path
            return log_path()
        except Exception:
            return "(نامشخص)"

    # ------------------ تشخیص خودکار از نرم‌افزار ریموت ------------------
    def detect_remote(self, silent=True):
        """
        نام/IP دستگاه متصل را از پنجرهٔ DameWare می‌خواند و فیلد سیستم را پر می‌کند.
        silent=True یعنی حالت خودکار (بدون پیام خطا و بدون بازنویسی فیلدهای پرشده).
        """
        # در حالتِ خودکار فقط وقتی واقعاً اتصال TCP برقرار است پر کن؛ وگرنه
        # پنجرهٔ بازماندهٔ DameWare سیستمِ قبلی را به‌اشتباه نشان می‌دهد.
        if silent and not is_remote_connected():
            return
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
            # نامِ واقعیِ کارمند از دیتابیس بر نامِ حدس‌زده‌شده از روی سیستم اولویت دارد
            if emp.full_name and (not silent or self._name_is_auto()):
                self.txt_req_name.setText(emp.full_name)
                self._last_derived = ""  # این نام واقعی است، دیگر حدسی نیست

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

    def get_checked_tasks(self, root=None, checked=None):
        if checked is None: checked = []
        iterator = range(self.task_tree.topLevelItemCount()) if root is None else range(root.childCount())
        for i in iterator:
            item = self.task_tree.topLevelItem(i) if root is None else root.child(i)
            if item.checkState(0) == Qt.Checked:
                checked.append(item.data(0, Qt.UserRole))
            self.get_checked_tasks(item, checked)
        return checked

    def _checked_task_titles(self, root=None, titles=None):
        """عنوانِ همهٔ مواردِ تیک‌خورده را برای ساختِ توضیح خودکار برمی‌گرداند."""
        if titles is None:
            titles = []
        count = self.task_tree.topLevelItemCount() if root is None else root.childCount()
        for i in range(count):
            item = self.task_tree.topLevelItem(i) if root is None else root.child(i)
            if item.checkState(0) == Qt.Checked:
                titles.append(item.text(0))
            self._checked_task_titles(item, titles)
        return titles

    def save_record(self):
        name = self.txt_req_name.text().strip()
        system = self.txt_system.text().strip()
        tasks = self.get_checked_tasks()

        if not tasks:
            QMessageBox.warning(self, "خطا", "انتخاب حداقل یک عملیات الزامی است.")
            return
        # نام شخص وقتی نام سیستم پر است اجباری نیست؛ در این حالت از روی سیستم ساخته می‌شود
        if not name:
            name = derive_person_name(system) or system
        if not name:
            QMessageBox.warning(self, "خطا", "نام شخص یا نام سیستم را وارد کنید.")
            return

        employee = self.db.query(Employee).filter_by(full_name=name).first()
        if not employee:
            employee = Employee(full_name=name, internal_extension=self.txt_req_ext.text().strip())
            self.db.add(employee)
            self.db.flush()

        # اگر توضیحی وارد نشده باشد، از روی مواردِ تیک‌خورده یک توضیح کوتاهِ خودکار بساز
        description = self.txt_notes.toPlainText().strip()
        if not description:
            description = "، ".join(self._checked_task_titles())

        record = ServiceRecord(
            technician_id=self.technician.id,
            requester_employee_id=employee.id,
            technician_name_snapshot=self.technician.full_name,
            requester_name_snapshot=employee.full_name,
            requester_extension_snapshot=self.txt_req_ext.text().strip(),
            system_name_snapshot=system,
            short_description=description
        )
        self.db.add(record)

        # کلید حل مشکل ثبت نشدن تیک‌ها این دستور است!
        self.db.flush()

        for task_id in tasks:
            self.db.add(ServiceRecordTask(service_record_id=record.id, task_id=task_id))

        self.db.commit()
        QMessageBox.information(self, "موفق", "گزارش شما سریعاً ثبت شد.")

        self._last_derived = ""
        self._clear_suggestion()
        self.txt_req_name.clear(); self.txt_req_ext.clear()
        self.txt_system.clear(); self.txt_notes.clear()
        self.txt_task_search.clear()
        self.load_data()
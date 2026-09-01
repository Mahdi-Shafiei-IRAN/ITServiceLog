from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                               QComboBox, QMessageBox, QAbstractItemView)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from database.models import Technician

class TechniciansPage(QWidget):
    def __init__(self, db_session: Session, current_technician=None):
        super().__init__()
        self.db = db_session
        self.current_technician = current_technician
        self.techs = []          # لیست کارشناسان متناظر با ردیف‌های جدول
        self.editing_id = None   # شناسه کارشناسی که در حال ویرایش است (None = افزودن جدید)
        self.setup_ui()
        self.load_technicians()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("مدیریت کاربران IT")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.lbl_mode = QLabel("حالت: افزودن کارشناس جدید")
        self.lbl_mode.setObjectName("Muted")
        layout.addWidget(self.lbl_mode)

        # فرم ثبت / ویرایش کارشناس IT
        form_layout = QHBoxLayout()
        form_layout.setSpacing(8)
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("نام و نام خانوادگی کارشناس...")

        self.txt_ext = QLineEdit()
        self.txt_ext.setPlaceholderText("داخلی...")

        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("نام کاربری (برای لاگین)...")

        self.txt_pass = QLineEdit()
        self.txt_pass.setPlaceholderText("رمز عبور...")

        self.cmb_role = QComboBox()
        self.cmb_role.addItems(["Technician", "Administrator"])

        btn_add = QPushButton("ثبت / ذخیره")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self.save_technician)

        btn_new = QPushButton("جدید")
        btn_new.setProperty("variant", "ghost")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.clicked.connect(self.clear_form)

        btn_delete = QPushButton("حذف")
        btn_delete.setProperty("variant", "danger")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self.delete_technician)

        form_layout.addWidget(self.txt_name)
        form_layout.addWidget(self.txt_ext)
        form_layout.addWidget(self.txt_user)
        form_layout.addWidget(self.txt_pass)
        form_layout.addWidget(self.cmb_role)
        form_layout.addWidget(btn_add)
        form_layout.addWidget(btn_new)
        form_layout.addWidget(btn_delete)
        layout.addLayout(form_layout)

        # جدول نمایش کارشناسان
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["شناسه", "نام", "داخلی", "نام کاربری", "نقش (Role)"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        layout.addWidget(self.table)

    def load_technicians(self):
        self.table.setRowCount(0)
        self.techs = self.db.query(Technician).filter_by(is_active=True).all()
        self.table.setRowCount(len(self.techs))

        for row, t in enumerate(self.techs):
            self.table.setItem(row, 0, QTableWidgetItem(str(t.id)))
            self.table.setItem(row, 1, QTableWidgetItem(t.full_name))
            self.table.setItem(row, 2, QTableWidgetItem(t.internal_extension or "-"))
            self.table.setItem(row, 3, QTableWidgetItem(t.username))
            self.table.setItem(row, 4, QTableWidgetItem("مدیر" if t.role == "Administrator" else "کارشناس"))

    def _selected_row(self):
        sel = self.table.selectionModel().selectedRows()
        if sel:
            return sel[0].row()
        return self.table.currentRow()

    def on_row_selected(self):
        """با انتخاب یک ردیف، اطلاعات آن کارشناس در فرم برای ویرایش بارگذاری می‌شود."""
        row = self._selected_row()
        if row < 0 or row >= len(self.techs):
            return
        t = self.techs[row]
        self.editing_id = t.id
        self.txt_name.setText(t.full_name)
        self.txt_ext.setText(t.internal_extension or "")
        self.txt_user.setText(t.username)
        self.txt_pass.clear()
        self.txt_pass.setPlaceholderText("برای حفظ رمز فعلی خالی بگذارید...")
        self.cmb_role.setCurrentText(t.role)
        self.lbl_mode.setText(f"حالت: ویرایش کارشناس «{t.full_name}» (#{t.id})")

    def clear_form(self):
        """بازگشت به حالت افزودن کارشناس جدید."""
        self.editing_id = None
        self.txt_name.clear(); self.txt_ext.clear()
        self.txt_user.clear(); self.txt_pass.clear()
        self.txt_pass.setPlaceholderText("رمز عبور...")
        self.cmb_role.setCurrentIndex(0)
        self.table.clearSelection()
        self.lbl_mode.setText("حالت: افزودن کارشناس جدید")

    def save_technician(self):
        name = self.txt_name.text().strip()
        user = self.txt_user.text().strip()
        pwd = self.txt_pass.text().strip()
        role = self.cmb_role.currentText()
        ext = self.txt_ext.text().strip()

        if not name or not user:
            return QMessageBox.warning(self, "خطا", "نام و نام کاربری الزامی است.")

        # جلوگیری از نام کاربری تکراری (به‌جز خودِ کارشناس در حال ویرایش)
        existing = self.db.query(Technician).filter_by(username=user).first()
        if existing and existing.id != self.editing_id:
            return QMessageBox.warning(self, "خطا", "این نام کاربری از قبل وجود دارد.")

        if self.editing_id:
            # --- ویرایش ---
            tech = self.db.get(Technician, self.editing_id)
            if not tech:
                return QMessageBox.warning(self, "خطا", "کارشناس یافت نشد.")
            tech.full_name = name
            tech.internal_extension = ext
            tech.username = user
            tech.role = role
            if pwd:  # فقط اگر رمز جدید وارد شده باشد
                tech.password_hash = pwd
            self.db.commit()
            QMessageBox.information(self, "موفق", "اطلاعات کارشناس با موفقیت به‌روزرسانی شد.")
        else:
            # --- افزودن جدید ---
            if not pwd:
                return QMessageBox.warning(self, "خطا", "برای کارشناس جدید، رمز عبور الزامی است.")
            new_tech = Technician(
                full_name=name,
                internal_extension=ext,
                username=user,
                password_hash=pwd,  # در سیستم‌های بزرگ‌تر باید هش شود
                role=role
            )
            self.db.add(new_tech)
            self.db.commit()
            QMessageBox.information(self, "موفق", "کارشناس جدید با موفقیت ثبت شد.")

        self.clear_form()
        self.load_technicians()

    def delete_technician(self):
        row = self._selected_row()
        if row < 0 or row >= len(self.techs):
            return QMessageBox.information(self, "توجه", "لطفاً ابتدا یک کارشناس را از جدول انتخاب کنید.")
        tech = self.techs[row]

        # جلوگیری از حذف حساب خودِ کاربر جاری
        if self.current_technician and tech.id == self.current_technician.id:
            return QMessageBox.warning(self, "خطا", "نمی‌توانید حساب کاربری خودتان را حذف کنید.")

        # جلوگیری از حذف آخرین مدیر فعال
        if tech.role == "Administrator":
            admin_count = self.db.query(Technician).filter_by(role="Administrator", is_active=True).count()
            if admin_count <= 1:
                return QMessageBox.warning(self, "خطا", "حذف تنها مدیر سیستم مجاز نیست.")

        confirm = QMessageBox.question(
            self, "تأیید حذف",
            f"آیا از حذف کارشناس «{tech.full_name}» مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        # حذف نرم (غیرفعال‌سازی) تا گزارش‌های قبلی این کارشناس حفظ شوند
        tech.is_active = False
        self.db.commit()
        QMessageBox.information(self, "موفق", "کارشناس با موفقیت حذف شد.")
        self.clear_form()
        self.load_technicians()

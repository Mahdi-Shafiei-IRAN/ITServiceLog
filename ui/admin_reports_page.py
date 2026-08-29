from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QComboBox, QFileDialog, QMessageBox, QAbstractItemView)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from database.models import ServiceRecord, Technician
from reports.excel_exporter import export_records_to_excel

class AdminReportsPage(QWidget):
    def __init__(self, db_session: Session):
        super().__init__()
        self.db = db_session
        self.records = []
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # ---------------- بخش فیلترها و جستجو ----------------
        top_bar = QHBoxLayout()
        
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجوی سراسری (نام، داخلی، سیستم، عملیات)...")
        self.txt_search.textChanged.connect(self.filter_data)

        self.cmb_tech = QComboBox()
        self.cmb_tech.addItem("همه کارشناسان IT", None)
        self.cmb_tech.currentIndexChanged.connect(self.filter_data)

        btn_refresh = QPushButton("بروزرسانی اطلاعات")
        btn_refresh.clicked.connect(self.load_data)

        btn_export = QPushButton("خروجی اکسل (Excel)")
        btn_export.setStyleSheet("background-color: #10B981; color: white; padding: 6px 15px; font-weight: bold; border-radius: 4px;")
        btn_export.clicked.connect(self.export_to_excel)

        top_bar.addWidget(QLabel("جستجو:"))
        top_bar.addWidget(self.txt_search, stretch=2)
        top_bar.addWidget(QLabel("کارشناس:"))
        top_bar.addWidget(self.cmb_tech, stretch=1)
        top_bar.addWidget(btn_refresh)
        top_bar.addWidget(btn_export)
        
        layout.addLayout(top_bar)

        # ---------------- جدول نمایش داده‌ها ----------------
        self.table = QTableWidget()

        # در تابع setup_ui:
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ردیف", "کد رهگیری", "تاریخ", "ساعت", "مراجعه‌کننده", "داخلی", "سیستم", "کارشناس IT", "عملیات انجام‌شده"
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { background-color: white; alternate-background-color: #F8FAFC; border-radius: 6px; }
            QHeaderView::section { background-color: #F1F5F9; font-weight: bold; padding: 8px; }
        """)

        header = self.table.horizontalHeader()
        for i in range(7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

        layout.addWidget(self.table, stretch=1)
        
        self.lbl_status = QLabel("تعداد رکوردها: ۰")
        self.lbl_status.setStyleSheet("color: #64748B; font-weight: bold;")
        layout.addWidget(self.lbl_status)

    def load_data(self):
        """بارگذاری لیست کارشناسان و تمامی رکوردها از دیتابیس"""
        # پر کردن لیست کشویی کارشناسان
        self.cmb_tech.blockSignals(True)
        self.cmb_tech.clear()
        self.cmb_tech.addItem("همه کارشناسان IT", None)
        techs = self.db.query(Technician).filter_by(is_active=True).all()
        for t in techs:
            self.cmb_tech.addItem(t.full_name, t.id)
        self.cmb_tech.blockSignals(False)

        # دریافت همه رکوردها
        self.all_records = self.db.query(ServiceRecord).order_by(ServiceRecord.created_at.desc()).all()
        self.filter_data()

    def filter_data(self):
        """اعمال جستجوی متنی و فیلتر کارشناس روی داده‌ها"""
        search_text = self.txt_search.text().strip().lower()
        selected_tech_id = self.cmb_tech.currentData()

        self.records = []
        for rec in self.all_records:
            # فیلتر کارشناس
            if selected_tech_id and rec.technician_id != selected_tech_id:
                continue
            
            # فیلتر جستجوی متنی
            tasks_str = " ".join([t.task.title for t in rec.tasks if t.task]).lower()
            match = (
                search_text in str(rec.id)
                or search_text in (rec.requester_name_snapshot or "").lower()
                or search_text in (rec.requester_extension_snapshot or "").lower()
                or search_text in (rec.system_name_snapshot or "").lower()
                or search_text in (rec.short_description or "").lower()
                or search_text in (rec.technician_name_snapshot or "").lower()
                or search_text in tasks_str
            )
            
            if match:
                self.records.append(rec)

        self.populate_table(self.records)


    # جایگزین کردن تابع populate_table:
    def populate_table(self, records):
        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            tasks_preview = " | ".join([t.task.title for t in rec.tasks if t.task]) or "-"
            
            items = [
                QTableWidgetItem(str(row + 1)),
                QTableWidgetItem(f"#{rec.id}"),
                QTableWidgetItem(rec.created_at.strftime("%Y/%m/%d")),
                QTableWidgetItem(rec.created_at.strftime("%H:%M")),
                QTableWidgetItem(rec.requester_name_snapshot or "-"),
                QTableWidgetItem(rec.requester_extension_snapshot or "-"),
                QTableWidgetItem(rec.system_name_snapshot or "-"),
                QTableWidgetItem(rec.technician_name_snapshot or "-"),
                QTableWidgetItem(tasks_preview)
            ]
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter if col < 8 else Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row, col, item)
        self.lbl_status.setText(f"تعداد رکوردهای در حال نمایش: {len(records)}")

    # جایگزین کردن تابع filter_data:
    def filter_data(self):
        search_query = self.txt_search.text().strip().lower()
        search_words = search_query.split() if search_query else []
        selected_tech_id = self.cmb_tech.currentData()

        self.records = []
        for rec in self.all_records:
            if selected_tech_id and rec.technician_id != selected_tech_id:
                continue
            
            if search_words:
                tasks_str = " ".join([t.task.title for t in rec.tasks if t.task]).lower()
                searchable_text = f"{rec.id} {rec.requester_name_snapshot or ''} {rec.requester_extension_snapshot or ''} {rec.system_name_snapshot or ''} {rec.short_description or ''} {rec.technician_name_snapshot or ''} {tasks_str}".lower()
                
                if not all(word in searchable_text for word in search_words):
                    continue # اگر حتی یکی از کلمات مچ نشد این رکورد را رد کن
            
            self.records.append(rec)

        self.populate_table(self.records)

    def export_to_excel(self):
        if not self.records:
            return QMessageBox.warning(self, "خطا", "رکوردی برای خروجی گرفتن وجود ندارد.")

        # باز کردن پنجره ذخیره فایل
        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل اکسل", "IT_Reports.xlsx", "Excel Files (*.xlsx)"
        )
        
        if filepath:
            try:
                # ارسال رکوردهای فیلتر شده به ماژول اکسل
                selected_tech_id = self.cmb_tech.currentData()
                selected_tech = self.db.query(Technician).get(selected_tech_id) if selected_tech_id else None
                
                export_records_to_excel(filepath, self.records, technician=selected_tech)
                QMessageBox.information(self, "موفق", f"فایل اکسل با موفقیت ذخیره شد:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "خطا", f"خطا در ایجاد فایل اکسل:\n{str(e)}")
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QTextEdit, QFrame, QAbstractItemView, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from database.models import ServiceRecord
from reports.excel_exporter import export_records_to_excel
from ui.record_edit_dialog import EditServiceRecordDialog, delete_service_record


class RecordDetailDialog(QDialog):
    """Modern popup window to view the complete details of a single record."""
    def __init__(self, record: ServiceRecord, parent=None):
        super().__init__(parent)
        self.setWindowTitle("جزئیات گزارش مراجعه")
        self.setFixedSize(480, 520)
        self.setLayoutDirection(Qt.RightToLeft)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(f"گزارش شماره #{record.id}")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        # Details Box
        info_frame = QFrame()
        info_frame.setObjectName("Card")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        
        info_layout.addWidget(QLabel(f"<b>مراجعه‌کننده:</b> {record.requester_name_snapshot} (داخلی: {record.requester_extension_snapshot})"))
        info_layout.addWidget(QLabel(f"<b>سیستم / دارایی:</b> {record.system_name_snapshot or 'ثبت نشده'}"))
        info_layout.addWidget(QLabel(f"<b>کارشناس رسیدگی‌کننده:</b> {record.technician_name_snapshot}"))
        info_layout.addWidget(QLabel(f"<b>زمان ثبت:</b> {record.created_at.strftime('%Y/%m/%d - %H:%M')}"))
        layout.addWidget(info_frame)

        # Selected Tasks list
        layout.addWidget(QLabel("<b>عملیات انجام‌شده:</b>"))
        tasks_text = QTextEdit()
        tasks_text.setReadOnly(True)
        task_names = [f"• {st.task.title}" for st in record.tasks if st.task]
        tasks_text.setPlainText("\n".join(task_names) if task_names else "موردی ثبت نشده است.")
        layout.addWidget(tasks_text)

        # Short Note
        layout.addWidget(QLabel("<b>توضیح کوتاه:</b>"))
        note_text = QTextEdit()
        note_text.setReadOnly(True)
        note_text.setPlainText(record.short_description or "بدون توضیح.")
        note_text.setMaximumHeight(80)
        layout.addWidget(note_text)

        # Close button
        btn_close = QPushButton("بستن")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class MyReportsPage(QWidget):
    def __init__(self, db_session: Session, current_technician):
        super().__init__()
        self.db = db_session
        self.technician = current_technician
        self.records = []
        self.displayed = []
        self.setup_ui()
        self.load_records()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header + Live Search bar
        top_bar = QHBoxLayout()
        title = QLabel("گزارش‌های ثبت‌شده توسط من")
        title.setObjectName("PageTitle")
        top_bar.addWidget(title)

        top_bar.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو در مراجعین، سیستم، کار یا توضیحات...")
        self.txt_search.setFixedWidth(300)
        self.txt_search.textChanged.connect(self.filter_records)
        top_bar.addWidget(self.txt_search)

        btn_export = QPushButton("خروجی اکسل")
        btn_export.setProperty("variant", "success")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self.export_to_excel)
        top_bar.addWidget(btn_export)

        btn_edit = QPushButton("ویرایش")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(self.edit_selected)
        top_bar.addWidget(btn_edit)

        btn_delete = QPushButton("حذف")
        btn_delete.setProperty("variant", "danger")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self.delete_selected)
        top_bar.addWidget(btn_delete)

        btn_refresh = QPushButton("بروزرسانی")
        btn_refresh.setProperty("variant", "ghost")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.load_records)
        top_bar.addWidget(btn_refresh)

        layout.addLayout(top_bar)


        # در تابع setup_ui تیتر جدول را عوض کنید:
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ردیف", "کد رهگیری", "تاریخ", "ساعت", "مراجعه‌کننده", "داخلی", "سیستم", "عملیات انجام‌شده"
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.show_record_details)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)

        layout.addWidget(self.table, stretch=1)

        # Footer Status bar
        self.lbl_status = QLabel("تعداد کل گزارش‌های شما: ۰")
        self.lbl_status.setObjectName("Muted")
        layout.addWidget(self.lbl_status)

    def load_records(self):
        """Fetch all records belonging to the logged-in technician."""
        self.records = (
            self.db.query(ServiceRecord)
            .filter_by(technician_id=self.technician.id)
            .order_by(ServiceRecord.created_at.desc())
            .all()
        )
        self.populate_table(self.records)

    def show_record_details(self, index):
        row = index.row()
        record_id_item = self.table.item(row, 0)
        if record_id_item:
            record_id = int(record_id_item.text())
            record = next((r for r in self.records if r.id == record_id), None)
            if record:
                dialog = RecordDetailDialog(record, self)
                dialog.exec()



    def populate_table(self, records):
        self.displayed = list(records)  # لیست رکوردهای در حال نمایش (برای ویرایش/حذف)
        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            tasks_preview = " | ".join([t.task.title for t in rec.tasks if t.task]) or "-"

            items = [
                QTableWidgetItem(str(row + 1)), # ردیف از 1 شروع می‌شود (برای خود کارشناس)
                QTableWidgetItem(f"#{rec.id}"), # کد دیتابیس (برای ارجاع به مدیر)
                QTableWidgetItem(rec.created_at.strftime("%Y/%m/%d")),
                QTableWidgetItem(rec.created_at.strftime("%H:%M")),
                QTableWidgetItem(rec.requester_name_snapshot or "-"),
                QTableWidgetItem(rec.requester_extension_snapshot or "-"),
                QTableWidgetItem(rec.system_name_snapshot or "-"),
                QTableWidgetItem(tasks_preview)
            ]
            items[0].setData(Qt.UserRole, rec.id)

            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter if col < 7 else Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row, col, item)

        self.lbl_status.setText(f"نمایش {len(records)} گزارش | دابل کلیک روی ردیف برای جزئیات.")

    # الگوریتم جدید سرچ هوشمند کلمه به کلمه:
    def filter_records(self, query: str):
        query = query.strip().lower()
        if not query:
            self.populate_table(self.records)
            return

        filtered = []
        search_words = query.split() # کلمات سرچ شده را جدا می‌کند
        
        for rec in self.records:
            tasks_str = " ".join([t.task.title for t in rec.tasks if t.task]).lower()
            # ساخت یک متن یکپارچه از کل دیتای رکورد
            searchable_text = f"{rec.id} {rec.requester_name_snapshot or ''} {rec.requester_extension_snapshot or ''} {rec.system_name_snapshot or ''} {rec.short_description or ''} {tasks_str}".lower()
            
            # اگر "تمام" کلمات سرچ شده در متن رکورد وجود داشت آن را نمایش بده
            if all(word in searchable_text for word in search_words):
                filtered.append(rec)

        self.populate_table(filtered)

    def _selected_record(self):
        """رکورد متناظر با ردیف انتخاب‌شده در جدول را برمی‌گرداند."""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.displayed):
            QMessageBox.information(self, "توجه", "لطفاً ابتدا یک گزارش را از جدول انتخاب کنید.")
            return None
        return self.displayed[row]

    def edit_selected(self):
        record = self._selected_record()
        if not record:
            return
        dialog = EditServiceRecordDialog(self.db, record, self)
        if dialog.exec() == QDialog.Accepted:
            self.load_records()

    def delete_selected(self):
        record = self._selected_record()
        if not record:
            return
        if delete_service_record(self.db, record, self):
            self.load_records()

    def export_to_excel(self):
        if not self.displayed:
            QMessageBox.warning(self, "خطا", "گزارشی برای خروجی گرفتن وجود ندارد.")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل اکسل", "My_Reports.xlsx", "Excel Files (*.xlsx)"
        )
        if not filepath:
            return
        try:
            export_records_to_excel(filepath, self.displayed, technician=self.technician)
            QMessageBox.information(self, "موفق", f"فایل اکسل ذخیره شد:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ایجاد فایل اکسل:\n{str(e)}")
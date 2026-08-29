from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QTextEdit, QFrame, QAbstractItemView
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import Session
from database.models import ServiceRecord


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
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E293B;")
        layout.addWidget(title)

        # Details Box
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px;")
        info_layout = QVBoxLayout(info_frame)
        
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
        tasks_text.setStyleSheet("background-color: white; border: 1px solid #CBD5E1; border-radius: 4px; padding: 6px;")
        layout.addWidget(tasks_text)

        # Short Note
        layout.addWidget(QLabel("<b>توضیح کوتاه:</b>"))
        note_text = QTextEdit()
        note_text.setReadOnly(True)
        note_text.setPlainText(record.short_description or "بدون توضیح.")
        note_text.setMaximumHeight(80)
        note_text.setStyleSheet("background-color: white; border: 1px solid #CBD5E1; border-radius: 4px; padding: 6px;")
        layout.addWidget(note_text)

        # Close button
        btn_close = QPushButton("بستن")
        btn_close.setStyleSheet("background-color: #0284C7; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class MyReportsPage(QWidget):
    def __init__(self, db_session: Session, current_technician):
        super().__init__()
        self.db = db_session
        self.technician = current_technician
        self.records = []
        self.setup_ui()
        self.load_records()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header + Live Search bar
        top_bar = QHBoxLayout()
        title = QLabel("گزارش‌های ثبت‌شده توسط من")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1E293B;")
        top_bar.addWidget(title)

        top_bar.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو در مراجعین، سیستم، کار یا توضیحات...")
        self.txt_search.setFixedWidth(320)
        self.txt_search.textChanged.connect(self.filter_records)
        top_bar.addWidget(self.txt_search)

        btn_refresh = QPushButton("بروزرسانی")
        btn_refresh.setStyleSheet("background-color: #0F172A; color: white; padding: 6px 14px; border-radius: 4px;")
        btn_refresh.clicked.connect(self.load_records)
        top_bar.addWidget(btn_refresh)

        layout.addLayout(top_bar)

        # Modern Data Grid Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "شناسه", "تاریخ", "ساعت", "مراجعه‌کننده", "داخلی", "سیستم", "عملیات انجام‌شده"
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.show_record_details)

        # Table Styling
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                gridline-color: #F1F5F9;
                selection-background-color: #E0F2FE;
                selection-color: #0369A1;
            }
            QHeaderView::section {
                background-color: #F1F5F9;
                color: #475569;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #CBD5E1;
            }
        """)

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
        self.lbl_status.setStyleSheet("color: #64748B; font-size: 12px;")
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

    def populate_table(self, records):
        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            tasks_preview = ", ".join([t.task.title for t in rec.tasks if t.task]) or "-"

            items = [
                QTableWidgetItem(str(rec.id)),
                QTableWidgetItem(rec.created_at.strftime("%Y/%m/%d")),
                QTableWidgetItem(rec.created_at.strftime("%H:%M")),
                QTableWidgetItem(rec.requester_name_snapshot or "-"),
                QTableWidgetItem(rec.requester_extension_snapshot or "-"),
                QTableWidgetItem(rec.system_name_snapshot or "-"),
                QTableWidgetItem(tasks_preview)
            ]

            for col, item in enumerate(items):
                if col < 6:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

        self.lbl_status.setText(f"نمایش {len(records)} گزارش | برای مشاهده جزئیات کامل روی هر ردیف دابل کلیک کنید.")

    def filter_records(self, query: str):
        """Instant filtering across all columns."""
        query = query.strip().lower()
        if not query:
            self.populate_table(self.records)
            return

        filtered = []
        for rec in self.records:
            tasks_str = " ".join([t.task.title for t in rec.tasks if t.task]).lower()
            match = (
                query in str(rec.id)
                or query in (rec.requester_name_snapshot or "").lower()
                or query in (rec.requester_extension_snapshot or "").lower()
                or query in (rec.system_name_snapshot or "").lower()
                or query in (rec.short_description or "").lower()
                or query in tasks_str
            )
            if match:
                filtered.append(rec)
        self.populate_table(filtered)

    def show_record_details(self, index):
        row = index.row()
        record_id_item = self.table.item(row, 0)
        if record_id_item:
            record_id = int(record_id_item.text())
            record = next((r for r in self.records if r.id == record_id), None)
            if record:
                dialog = RecordDetailDialog(record, self)
                dialog.exec()
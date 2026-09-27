"""«کارهای شاخص IT» — پنل ثبت (صاحب کار) و تب گزارش (ادمین).

  • admin=False: فقط کارهای همان کاربر؛ افزودن، ویرایش، حذف و ثبت به‌روزرسانی.
  • admin=True : کارهای همه‌ی کاربران + فیلتر «ثبت‌کننده»؛ فقط‌خواندنی.
هر دو حالت نوار خلاصه‌ی بازه و خروجی اکسل دارند. همه‌ی عددها از
services.key_activity_service می‌آیند تا با فایل اکسل یکی باشند.
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QSplitter, QFrame,
                               QListWidget, QSpinBox, QDateEdit, QMessageBox, QFileDialog,
                               QProgressBar)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QDate, QItemSelection, QItemSelectionModel
from sqlalchemy.orm import selectinload

from database.models import (KeyActivity, Technician, KEY_STATUSES, KEY_STATUS_DONE,
                             KEY_STATUS_IN_PROGRESS, KEY_PRIORITIES, KEY_PRIORITY_TOP)
from reports.key_activities_exporter import export_key_activities_to_excel, default_filename
from services import key_activity_service as svc
from ui.key_activity_dialog import KeyActivityDialog
from ui.period_filter import PeriodFilter
from ui.theme import theme

_STATS = [
    ("done_in_period", "انجام‌شده در بازه"),
    ("in_progress", "در حال انجام"),
    ("started_in_period", "شروع‌شده در بازه"),
    ("updates_in_period", "به‌روزرسانی‌ها"),
]


def _dt(d):
    return d.strftime("%Y/%m/%d") if d else "-"


class _ActivityTable(QTableWidget):
    """QTableWidget با selectRow دستی.

    پیاده‌سازیِ پیش‌فرض Qt برای selectRow ستون را با
    logicalIndexAt(viewport().width()) پیدا می‌کند؛ در چیدمانِ راست‌به‌چپ (RTL) —
    که چیدمانِ همیشگیِ این برنامه است، نه فقط تست‌ها — این متد -۱ برمی‌گرداند و
    در نتیجه selectRow اصلاً هیچ سطری را انتخاب نمی‌کند و سیگنال
    itemSelectionChanged هم منتشر نمی‌شود. این یک باگِ واقعی در اجرای عادیِ
    برنامه است (نه فقط در رندر offscreen محیط تست)؛ پس این بازنویسیِ حداقلی —
    که همان انتخاب را مستقیماً از طریق selectionModel انجام می‌دهد — را حذف نکنید.
    """

    def selectRow(self, row):
        if self.columnCount() == 0 or not 0 <= row < self.rowCount():
            return
        model = self.model()
        sel = QItemSelection(model.index(row, 0), model.index(row, self.columnCount() - 1))
        self.selectionModel().select(sel, QItemSelectionModel.ClearAndSelect
                                     | QItemSelectionModel.Rows)
        self.selectionModel().setCurrentIndex(
            model.index(row, 0), QItemSelectionModel.Current | QItemSelectionModel.Rows)


class KeyActivitiesPage(QWidget):
    def __init__(self, db_session, technician, admin=False, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.technician = technician
        self.admin = admin
        self.all = []
        self.shown = []
        self.current = None
        self._current_id = None  # شناسه‌ی ساده؛ چون self.current بعد از commit/rollback expire می‌شود
        self.btn_new = None
        self.update_box = None
        self.cmb_owner = None
        self.setup_ui()
        self.load_data()

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("گزارش کارهای شاخص" if self.admin else "کارهای شاخص IT")
        title.setObjectName("PageTitle")
        head.addWidget(title)
        head.addStretch()
        if not self.admin:
            self.btn_new = QPushButton("+ کار شاخص جدید")
            self.btn_new.setProperty("variant", "success")
            self.btn_new.setCursor(Qt.PointingHandCursor)
            self.btn_new.clicked.connect(self.new_activity)
            head.addWidget(self.btn_new)
        layout.addLayout(head)

        # نوار خلاصه‌ی بازه (همان عددهای شیت «جمع‌بندی»)
        strip = QHBoxLayout()
        self.stat_labels = {}
        for key, caption in _STATS:
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            value = QLabel("0")
            value.setObjectName("SectionTitle")
            cap = QLabel(caption)
            cap.setObjectName("Muted")
            card_layout.addWidget(value)
            card_layout.addWidget(cap)
            self.stat_labels[key] = value
            strip.addWidget(card)
        layout.addLayout(strip)

        bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو در عنوان، شرح، نتیجه و به‌روزرسانی‌ها...")
        self.txt_search.textChanged.connect(self.apply_filters)
        bar.addWidget(QLabel("جستجو:"))
        bar.addWidget(self.txt_search, 2)
        self.cmb_status = self._filter_combo("همه‌ی وضعیت‌ها", KEY_STATUSES)
        self.cmb_category = self._filter_combo("همه‌ی دسته‌ها", [])
        self.cmb_priority = self._filter_combo("همه‌ی اهمیت‌ها", KEY_PRIORITIES)
        bar.addWidget(QLabel("وضعیت:"))
        bar.addWidget(self.cmb_status, 1)
        bar.addWidget(QLabel("دسته:"))
        bar.addWidget(self.cmb_category, 1)
        bar.addWidget(QLabel("اهمیت:"))
        bar.addWidget(self.cmb_priority, 1)
        if self.admin:
            self.cmb_owner = self._filter_combo("همه‌ی ثبت‌کننده‌ها", [])
            bar.addWidget(QLabel("ثبت‌کننده:"))
            bar.addWidget(self.cmb_owner, 1)
        layout.addLayout(bar)

        bar2 = QHBoxLayout()
        self.period = PeriodFilter(default="this_month")
        self.period.changed.connect(self.apply_filters)
        bar2.addWidget(self.period)
        bar2.addStretch()
        btn_refresh = QPushButton("بروزرسانی")
        btn_refresh.setProperty("variant", "ghost")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(lambda: self.load_data())
        btn_export = QPushButton("خروجی اکسل")
        btn_export.setProperty("variant", "success")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self.export)
        bar2.addWidget(btn_refresh)
        bar2.addWidget(btn_export)
        layout.addLayout(bar2)

        splitter = QSplitter(Qt.Horizontal)
        headers = self._headers()
        self._progress_col = headers.index("پیشرفت")
        self._priority_col = headers.index("اهمیت")
        self.table = _ActivityTable()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for i in range(len(headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection)
        if not self.admin:
            self.table.doubleClicked.connect(lambda *_: self.edit_activity())
        splitter.addWidget(self.table)
        splitter.addWidget(self._build_detail())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("Muted")
        layout.addWidget(self.lbl_count)

    def _filter_combo(self, all_label, options):
        cmb = QComboBox()
        cmb.addItem(all_label, None)
        for opt in options:
            cmb.addItem(opt, opt)
        cmb.currentIndexChanged.connect(self.apply_filters)
        return cmb

    def _headers(self):
        cols = ["عنوان"]
        if self.admin:
            cols.append("ثبت‌کننده")
        return cols + ["دسته", "اهمیت", "وضعیت", "پیشرفت", "شروع", "آخرین به‌روزرسانی"]

    def _build_detail(self):
        panel = QFrame()
        panel.setObjectName("Card")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        self.lbl_title = QLabel("")
        self.lbl_title.setObjectName("SectionTitle")
        self.lbl_title.setWordWrap(True)
        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("Muted")
        self.lbl_meta.setWordWrap(True)
        self.lbl_description = QLabel("")
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_result = QLabel("")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        for w in (self.lbl_title, self.lbl_meta, self.lbl_description, self.lbl_result):
            lay.addWidget(w)

        timeline_title = QLabel("تاریخچه‌ی به‌روزرسانی‌ها")
        timeline_title.setObjectName("SectionTitle")
        lay.addWidget(timeline_title)
        self.lst_timeline = QListWidget()
        self.lst_timeline.setWordWrap(True)
        lay.addWidget(self.lst_timeline, 1)

        if not self.admin:
            self.update_box = QFrame()
            ul = QVBoxLayout(self.update_box)
            ul.setContentsMargins(0, 0, 0, 0)
            ul.setSpacing(6)
            row = QHBoxLayout()
            self.date_update = QDateEdit()
            self.date_update.setCalendarPopup(True)
            self.date_update.setDisplayFormat("yyyy/MM/dd")
            self.date_update.setDate(QDate.currentDate())
            self.spn_update_progress = QSpinBox()
            self.spn_update_progress.setRange(0, 100)
            self.spn_update_progress.setSuffix(" ٪")
            self.cmb_update_status = QComboBox()
            self.cmb_update_status.addItems(KEY_STATUSES)
            row.addWidget(QLabel("تاریخ:"))
            row.addWidget(self.date_update)
            row.addWidget(QLabel("پیشرفت:"))
            row.addWidget(self.spn_update_progress)
            row.addWidget(QLabel("وضعیت:"))
            row.addWidget(self.cmb_update_status, 1)
            ul.addLayout(row)
            self.txt_update = QLineEdit()
            self.txt_update.setPlaceholderText("چه کاری انجام شد؟ (مثلاً: استوریج خریداری و نصب شد)")
            ul.addWidget(self.txt_update)
            self.btn_add_update = QPushButton("ثبت به‌روزرسانی")
            self.btn_add_update.setCursor(Qt.PointingHandCursor)
            self.btn_add_update.clicked.connect(self.add_update)
            ul.addWidget(self.btn_add_update)
            lay.addWidget(self.update_box)

            actions = QHBoxLayout()
            self.btn_edit = QPushButton("ویرایش")
            self.btn_edit.setProperty("variant", "ghost")
            self.btn_edit.setCursor(Qt.PointingHandCursor)
            self.btn_edit.clicked.connect(self.edit_activity)
            self.btn_delete = QPushButton("حذف")
            self.btn_delete.setProperty("variant", "danger")
            self.btn_delete.setCursor(Qt.PointingHandCursor)
            self.btn_delete.clicked.connect(self.delete_activity)
            actions.addStretch()
            actions.addWidget(self.btn_edit)
            actions.addWidget(self.btn_delete)
            lay.addLayout(actions)

        self._show_detail(None)
        return panel

    # ------------------------------------------------------------ داده‌ها
    def load_data(self, select_id=None):
        if select_id is None:
            select_id = self._current_id
        self._refresh_combo(self.cmb_category,
                            [(c, c) for c in svc.category_suggestions(self.db)])
        # eager-load به‌روزرسانی‌ها تا یک پرس‌وجوی شبکه‌ای جدا برای هر کار لازم نشود
        query = self.db.query(KeyActivity).options(selectinload(KeyActivity.updates))
        if self.admin:
            owner_ids = {tid for (tid,) in self.db.query(KeyActivity.technician_id).distinct()}
            techs = self.db.query(Technician).order_by(Technician.full_name).all()
            self._refresh_combo(self.cmb_owner, [(t.full_name, t.id) for t in techs
                                                 if t.can_log_key_activities or t.id in owner_ids])
        else:
            query = query.filter(KeyActivity.technician_id == self.technician.id)
        self.all = query.all()
        self.apply_filters(select_id=select_id)

    def _refresh_combo(self, combo, items):
        """گزینه‌ها را تازه می‌کند (به‌جز «همه») و انتخاب فعلی را حفظ می‌کند."""
        current = combo.currentData()
        combo.blockSignals(True)
        while combo.count() > 1:
            combo.removeItem(1)
        for label, data in items:
            combo.addItem(label, data)
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def apply_filters(self, *_, select_id=None):
        if select_id is None:
            select_id = self._current_id
        rng = self.period.date_range()
        filtered = svc.filter_activities(
            self.all, rng=rng,
            status=self.cmb_status.currentData(),
            category=self.cmb_category.currentData(),
            priority=self.cmb_priority.currentData(),
            owner_id=self.cmb_owner.currentData() if self.cmb_owner is not None else None,
            words=self.txt_search.text().split())
        self.shown = svc.sort_activities(filtered)
        self._fill_table()
        summary = svc.summarize(self.shown, rng)
        for key, label in self.stat_labels.items():
            label.setText(str(summary[key]))
        self._select(select_id)

    def _fill_table(self):
        t = self.table
        t.blockSignals(True)
        t.clearSelection()
        t.setRowCount(len(self.shown))
        danger = QColor(theme.palette["danger"])
        for row, a in enumerate(self.shown):
            values = [a.title]
            if self.admin:
                values.append(a.technician_name_snapshot or "-")
            values += [a.category or "-", a.priority or "-", a.status or "-", "",
                       _dt(a.start_date), _dt(svc.last_update_date(a))]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment((Qt.AlignRight if col == 0 else Qt.AlignCenter)
                                      | Qt.AlignVCenter)
                if a.priority == KEY_PRIORITY_TOP:
                    if col == 0:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    elif col == self._priority_col:
                        item.setForeground(danger)
                t.setItem(row, col, item)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(a.progress or 0)
            bar.setFormat("%p٪")
            bar.setAlignment(Qt.AlignCenter)
            t.setCellWidget(row, self._progress_col, bar)
        t.blockSignals(False)
        self.lbl_count.setText(f"تعداد کارهای نمایش‌داده‌شده: {len(self.shown)}")

    def _select(self, select_id):
        row = -1
        if select_id is not None:
            row = next((i for i, a in enumerate(self.shown) if a.id == select_id), -1)
        if row >= 0:
            self.table.selectRow(row)
        else:
            self.current = None
            self._current_id = None
            self._show_detail(None)

    def _on_selection(self):
        rows = self.table.selectionModel().selectedRows()
        row = rows[0].row() if rows else -1
        self.current = self.shown[row] if 0 <= row < len(self.shown) else None
        self._current_id = self.current.id if self.current is not None else None
        self._show_detail(self.current)

    def _show_detail(self, a):
        self.lst_timeline.clear()
        if a is None:
            self.lbl_title.setText("یک کار را از فهرست انتخاب کنید.")
            for w in (self.lbl_meta, self.lbl_description, self.lbl_result):
                w.setText("")
            self._set_detail_enabled(False)
            return
        self.lbl_title.setText(a.title)
        meta = [f"دسته: {a.category or '-'}", f"اهمیت: {a.priority or '-'}",
                f"وضعیت: {a.status or '-'}", f"پیشرفت: {a.progress or 0}٪",
                f"شروع: {_dt(a.start_date)}", f"اتمام: {_dt(a.end_date)}"]
        if self.admin:
            meta.insert(0, f"ثبت‌کننده: {a.technician_name_snapshot or '-'}")
        self.lbl_meta.setText("  •  ".join(meta))
        self.lbl_description.setText(f"شرح: {a.description or '-'}")
        self.lbl_result.setText(f"نتیجه: {a.result or '-'}")
        for u in svc.timeline(a):
            progress = f"{u.progress}٪" if u.progress is not None else "-"
            self.lst_timeline.addItem(
                f"{_dt(u.update_date)}  —  {progress}  —  {u.status or '-'}\n{u.text}")
        if not a.updates:
            self.lst_timeline.addItem("هنوز به‌روزرسانی‌ای ثبت نشده است.")
        if not self.admin:
            self.spn_update_progress.setValue(a.progress or 0)
            self.cmb_update_status.setCurrentText(a.status or KEY_STATUS_IN_PROGRESS)
            self.date_update.setDate(QDate.currentDate())
            self._set_detail_enabled(True)

    def _set_detail_enabled(self, enabled):
        if self.admin:
            return
        for w in (self.update_box, self.btn_edit, self.btn_delete):
            w.setEnabled(enabled)

    # ------------------------------------------------------------ عملیات
    def new_activity(self):
        if self.admin:
            return
        dlg = KeyActivityDialog(self.db, self.technician, parent=self)
        if dlg.exec():
            self.load_data(select_id=dlg.activity.id)

    def _fetch_current_or_warn(self):
        """کار انتخاب‌شده را دوباره از دیتابیس می‌خواند (self.current ممکن است expire شده باشد).

        اگر کار در همین فاصله (مثلاً از یک ماشین دیگر) حذف شده باشد، پیام می‌دهد،
        انتخاب را پاک می‌کند و صفحه را تازه می‌کند.
        """
        act = self.db.get(KeyActivity, self._current_id) if self._current_id is not None else None
        if act is None:
            QMessageBox.information(self, "توجه",
                                    "این کار دیگر وجود ندارد (احتمالاً حذف شده است).")
            self.current = None
            self._current_id = None
            self.load_data()
        return act

    def edit_activity(self):
        if self.admin or self._current_id is None:
            return
        act = self._fetch_current_or_warn()
        if act is None:
            return
        dlg = KeyActivityDialog(self.db, self.technician, activity=act, parent=self)
        dlg.exec()
        # همیشه (حتی اگر لغو شود) تازه می‌کنیم؛ چون دیالوگ در شکستِ ذخیره‌ی خودش هم
        # rollback می‌زند و self.all باید با سشن هم‌سو بماند.
        self.load_data()

    def add_update(self):
        if self.admin or self._current_id is None:
            return
        act = self._fetch_current_or_warn()
        if act is None:
            return
        text = self.txt_update.text().strip()
        if not text:
            QMessageBox.warning(self, "خطا", "متن به‌روزرسانی را وارد کنید.")
            return
        progress = self.spn_update_progress.value()
        status = self.cmb_update_status.currentText()
        if progress == 100 and status != KEY_STATUS_DONE:
            answer = QMessageBox.question(
                self, "تکمیل کار",
                "پیشرفت به ۱۰۰٪ رسید. وضعیت هم به «انجام شد» تغییر کند؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                status = KEY_STATUS_DONE
        try:
            svc.add_update(self.db, act, self.date_update.date().toPython(), text,
                           progress=progress, status=status, author=self.technician.full_name)
            self.db.commit()
        except ValueError as exc:
            self.db.rollback()
            QMessageBox.warning(self, "خطا", str(exc))
            self.load_data()
            return
        except Exception as exc:
            self.db.rollback()
            QMessageBox.critical(self, "خطا", f"ثبت به‌روزرسانی ممکن نشد:\n{exc}")
            self.load_data()
            return
        self.txt_update.clear()
        self.load_data()

    def delete_activity(self):
        if self.admin or self._current_id is None:
            return
        act = self._fetch_current_or_warn()
        if act is None:
            return
        confirm = QMessageBox.question(
            self, "تأیید حذف",
            f"کار شاخص «{act.title}» همراه با {len(act.updates)} به‌روزرسانی حذف شود؟ "
            "این عملیات قابل بازگشت نیست.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        try:
            self.db.delete(act)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            QMessageBox.critical(self, "خطا", f"حذف کار شاخص ممکن نشد:\n{exc}")
            self.load_data()
            return
        self.current = None
        self._current_id = None
        self.load_data()

    def export(self):
        if not self.shown:
            QMessageBox.warning(self, "خطا", "کاری برای خروجی گرفتن وجود ندارد.")
            return
        rng = self.period.date_range()
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل اکسل", default_filename(rng), "Excel Files (*.xlsx)")
        if not path:
            return
        owner = self.technician
        if self.admin:
            # اگر ادمین فیلتر «ثبت‌کننده» را زده باشد، شیت جمع‌بندی همان فرد را نام ببرد
            owner_id = self.cmb_owner.currentData() if self.cmb_owner is not None else None
            owner = self.db.get(Technician, owner_id) if owner_id is not None else None
        try:
            export_key_activities_to_excel(
                path, self.shown, rng, owner=owner, show_owner=self.admin)
            QMessageBox.information(self, "موفق", f"فایل اکسل ذخیره شد:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "خطا", f"خطا در ایجاد فایل اکسل:\n{exc}")

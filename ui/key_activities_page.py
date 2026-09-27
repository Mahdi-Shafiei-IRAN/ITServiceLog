"""«کارهای شاخص IT» — پنل ثبت (صاحب کار) و تب گزارش (ادمین).

  • admin=False: فقط کارهای همان کاربر؛ افزودن، ویرایش، حذف و ثبت به‌روزرسانی.
  • admin=True : کارهای همه‌ی کاربران + فیلتر «ثبت‌کننده»؛ فقط‌خواندنی.
هر دو حالت نوار خلاصه‌ی بازه و خروجی اکسل دارند. همه‌ی عددها از
services.key_activity_service می‌آیند تا با فایل اکسل یکی باشند.
"""
from html import escape

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                               QLineEdit, QPushButton, QComboBox, QTableWidget,
                               QTableWidgetItem, QHeaderView, QAbstractItemView, QSplitter,
                               QFrame, QSpinBox, QDateEdit, QMessageBox, QFileDialog,
                               QProgressBar, QStackedWidget, QScrollArea, QTextBrowser)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QDate, QItemSelection, QItemSelectionModel
from sqlalchemy.orm import selectinload

from database.models import (KeyActivity, Technician, KEY_STATUSES, KEY_STATUS_DONE,
                             KEY_STATUS_IN_PROGRESS, KEY_STATUS_PLANNED, KEY_STATUS_ON_HOLD,
                             KEY_STATUS_CANCELLED, KEY_PRIORITIES, KEY_PRIORITY_NORMAL,
                             KEY_PRIORITY_HIGH, KEY_PRIORITY_TOP)
from reports.key_activities_exporter import export_key_activities_to_excel, default_filename
from services import key_activity_service as svc
from ui.key_activity_dialog import KeyActivityDialog
from ui.period_filter import PeriodFilter
from ui.theme import theme, set_tone, tone_color

# (کلید خلاصه، عنوان، رنگ)
_STATS = [
    ("done_in_period", "انجام‌شده در بازه", "success"),
    ("in_progress", "در حال انجام", "primary"),
    ("started_in_period", "شروع‌شده در بازه", "warning"),
    ("updates_in_period", "به‌روزرسانی‌ها", None),
]

STATUS_TONES = {
    KEY_STATUS_PLANNED: "muted",
    KEY_STATUS_IN_PROGRESS: "primary",
    KEY_STATUS_DONE: "success",
    KEY_STATUS_ON_HOLD: "warning",
    KEY_STATUS_CANCELLED: "danger",
}
PRIORITY_TONES = {
    KEY_PRIORITY_NORMAL: "muted",
    KEY_PRIORITY_HIGH: "warning",
    KEY_PRIORITY_TOP: "danger",
}

_EMPTY_OWNER = ("هنوز کار شاخصی ثبت نکرده‌اید.\n\n"
                "با دکمه‌ی «+ کار شاخص جدید» اولین کار را ثبت کنید — هم کارهای یک‌روزه\n"
                "(مثل رفع یک قطعی) و هم پروژه‌های چندهفته‌ای که پیشرفتشان را به‌مرور ثبت می‌کنید.")
_EMPTY_ADMIN = ("هنوز هیچ کار شاخصی ثبت نشده است.\n\n"
                "مدیرها (Administrator) همیشه تب «کارهای شاخص IT» را برای ثبت دارند.\n"
                "برای اینکه کاربر دیگری هم بتواند ثبت کند، در «مدیریت کاربران IT»\n"
                "تیک «ثبت کارهای شاخص» را برایش بزنید (پس از ورود دوباره‌ی او فعال می‌شود).")
_EMPTY_FILTERED = ("در این بازه یا با این فیلترها کاری پیدا نشد.\n\n"
                   "بازه‌ی زمانی را به «همه‌ی زمان‌ها» تغییر دهید یا فیلترها را پاک کنید.")


def _dt(d):
    return d.strftime("%Y/%m/%d") if d else "-"


def _transparent(widget):
    """ظرفی که داخل کارت/سلول است نباید رنگِ پس‌زمینه‌ی صفحه را بکشد."""
    widget.setObjectName("Transparent")
    return widget


def _chip():
    lbl = QLabel("")
    lbl.setObjectName("Chip")
    return lbl


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
        self.timeline_items = []  # به‌روزرسانی‌های کارِ انتخاب‌شده، به همان ترتیب نمایش
        self.btn_new = None
        self.update_box = None
        self.cmb_owner = None
        self.setup_ui()
        self.load_data()
        # رنگ‌های جدول (وضعیت/اهمیت) و خط زمانی از پالت می‌آیند؛ با عوض شدن تم دوباره بکش
        theme.changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("گزارش کارهای شاخص" if self.admin else "کارهای شاخص IT")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "کارهای شاخص همه‌ی همکاران — فقط‌خواندنی؛ برای گزارش دوره‌ای خروجی اکسل بگیرید."
            if self.admin else
            "کارهای مهم خود را آزادانه ثبت کنید، پیشرفتشان را به‌روز کنید و برای گزارش به "
            "مدیریت خروجی اکسل بگیرید.")
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        head.addLayout(title_box, 1)
        if not self.admin:
            self.btn_new = QPushButton("+ کار شاخص جدید")
            self.btn_new.setProperty("variant", "success")
            self.btn_new.setCursor(Qt.PointingHandCursor)
            self.btn_new.clicked.connect(self.new_activity)
            head.addWidget(self.btn_new, 0, Qt.AlignTop)
        layout.addLayout(head)

        # نوار خلاصه‌ی بازه (همان عددهای شیت «جمع‌بندی»)
        strip = QHBoxLayout()
        strip.setSpacing(12)
        self.stat_labels = {}
        for key, caption, tone in _STATS:
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            card_layout.setSpacing(0)
            value = QLabel("0")
            value.setObjectName("StatValue")
            value.setAlignment(Qt.AlignCenter)
            if tone:
                value.setProperty("tone", tone)
            cap = QLabel(caption)
            cap.setObjectName("Muted")
            cap.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(value)
            card_layout.addWidget(cap)
            self.stat_labels[key] = value
            strip.addWidget(card)
        layout.addLayout(strip)

        bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو در عنوان، شرح، نتیجه و به‌روزرسانی‌ها...")
        self.txt_search.setClearButtonEnabled(True)
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
        btn_export.setToolTip("کارهای فعلیِ فهرست (با همین فیلترها و بازه) + گزارش پیشرفت + جمع‌بندی")
        btn_export.clicked.connect(self.export)
        bar2.addWidget(btn_refresh)
        bar2.addWidget(btn_export)
        layout.addLayout(bar2)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_list())
        splitter.addWidget(self._build_detail())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        # نسبت اولیه‌ی ۶۰/۴۰؛ وگرنه پنل جزئیات جا را می‌گیرد و عنوان‌ها بریده می‌شوند
        splitter.setSizes([600, 400])
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

    def _build_list(self):
        """جدول کارها + راهنمای «هنوز چیزی ثبت نشده» به‌جای جدول خالی."""
        headers = self._headers()
        self._progress_col = headers.index("پیشرفت")
        self._priority_col = headers.index("اهمیت")
        self._status_col = headers.index("وضعیت")
        self.table = _ActivityTable()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        header = self.table.horizontalHeader()
        for i in range(len(headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(self._progress_col, QHeaderView.Fixed)
        self.table.setColumnWidth(self._progress_col, 120)
        # ResizeToContents عرض تاریخ را با padding تم کمی کم حساب می‌کند و رقم آخر بریده
        # می‌شد؛ پس ستونِ «شروع» از روی اندازه‌ی واقعی فونت عرض ثابت می‌گیرد.
        start_col = headers.index("شروع")
        header.setSectionResizeMode(start_col, QHeaderView.Fixed)
        self.table.setColumnWidth(
            start_col, self.table.fontMetrics().horizontalAdvance("0000/00/00") + 36)
        self.table.itemSelectionChanged.connect(self._on_selection)
        if not self.admin:
            self.table.doubleClicked.connect(lambda *_: self.edit_activity())

        self.lbl_empty = QLabel("")
        self.lbl_empty.setObjectName("EmptyState")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setWordWrap(True)

        self.list_stack = QStackedWidget()
        self.list_stack.addWidget(self.table)
        self.list_stack.addWidget(self.lbl_empty)
        return self.list_stack

    def _build_detail(self):
        panel = QFrame()
        panel.setObjectName("Card")
        panel.setMinimumWidth(360)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)

        # محتوای جزئیات در یک ناحیه‌ی اسکرول‌دار تا روی مانیتورهای کوچک هم جا شود
        scroll = QScrollArea()
        scroll.setObjectName("Transparent")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setObjectName("Transparent")
        body = _transparent(QWidget())
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        # تا کاری انتخاب نشده، فقط همین راهنما (وسطِ پنل) دیده می‌شود
        self.lbl_placeholder = QLabel("یک کار را از فهرست انتخاب کنید تا جزئیات و "
                                      "تاریخچه‌ی پیشرفتش این‌جا نمایش داده شود.")
        self.lbl_placeholder.setObjectName("Muted")
        self.lbl_placeholder.setAlignment(Qt.AlignCenter)
        self.lbl_placeholder.setWordWrap(True)
        lay.addWidget(self.lbl_placeholder, 1)

        self.lbl_title = QLabel("")
        self.lbl_title.setObjectName("SectionTitle")
        self.lbl_title.setWordWrap(True)
        lay.addWidget(self.lbl_title)

        # چیپ‌های وضعیت / اهمیت / دسته + (در حالت صاحب کار) ویرایش و حذف
        self.chip_row = _transparent(QWidget())
        chips = QHBoxLayout(self.chip_row)
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        self.chip_status = _chip()
        self.chip_priority = _chip()
        self.chip_category = _chip()
        for c in (self.chip_status, self.chip_priority, self.chip_category):
            chips.addWidget(c)
        chips.addStretch()
        if not self.admin:
            self.btn_edit = QPushButton("ویرایش")
            self.btn_edit.setProperty("variant", "ghost")
            self.btn_edit.setCursor(Qt.PointingHandCursor)
            self.btn_edit.setToolTip("ویرایش مشخصات کار (دوبار کلیک روی ردیف هم همین کار را می‌کند)")
            self.btn_edit.clicked.connect(self.edit_activity)
            self.btn_delete = QPushButton("حذف")
            self.btn_delete.setProperty("variant", "danger")
            self.btn_delete.setCursor(Qt.PointingHandCursor)
            self.btn_delete.clicked.connect(self.delete_activity)
            chips.addWidget(self.btn_edit)
            chips.addWidget(self.btn_delete)
        lay.addWidget(self.chip_row)

        self.bar_progress = QProgressBar()
        self.bar_progress.setObjectName("DetailProgress")
        self.bar_progress.setRange(0, 100)
        self.bar_progress.setFormat("پیشرفت %p٪")
        lay.addWidget(self.bar_progress)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("Muted")
        self.lbl_meta.setWordWrap(True)
        lay.addWidget(self.lbl_meta)

        self.lbl_description_head = self._field_label("شرح کار")
        self.lbl_description = self._body_label()
        self.lbl_result_head = self._field_label("نتیجه / دستاورد")
        self.lbl_result = self._body_label()
        for w in (self.lbl_description_head, self.lbl_description,
                  self.lbl_result_head, self.lbl_result):
            lay.addWidget(w)

        # فرم ثبت پیشرفت پیش از تاریخچه، تا پرکاربردترین کار بدون اسکرول در دسترس باشد
        if not self.admin:
            self.update_box = QFrame()
            self.update_box.setObjectName("SubCard")
            ul = QVBoxLayout(self.update_box)
            ul.setContentsMargins(12, 10, 12, 12)
            ul.setSpacing(8)
            ul.addWidget(self._field_label("ثبت پیشرفت جدید"))
            grid = QGridLayout()
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(6)
            self.date_update = QDateEdit()
            self.date_update.setCalendarPopup(True)
            self.date_update.setDisplayFormat("yyyy/MM/dd")
            self.date_update.setDate(QDate.currentDate())
            self.spn_update_progress = QSpinBox()
            self.spn_update_progress.setRange(0, 100)
            self.spn_update_progress.setSuffix(" ٪")
            self.cmb_update_status = QComboBox()
            self.cmb_update_status.addItems(KEY_STATUSES)
            grid.addWidget(QLabel("تاریخ:"), 0, 0)
            grid.addWidget(self.date_update, 0, 1)
            grid.addWidget(QLabel("پیشرفت:"), 0, 2)
            grid.addWidget(self.spn_update_progress, 0, 3)
            grid.addWidget(QLabel("وضعیت:"), 1, 0)
            grid.addWidget(self.cmb_update_status, 1, 1, 1, 3)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)
            ul.addLayout(grid)
            self.txt_update = QLineEdit()
            self.txt_update.setPlaceholderText("چه کاری انجام شد؟ (مثلاً: استوریج خریداری و نصب شد)")
            self.txt_update.returnPressed.connect(self.add_update)
            ul.addWidget(self.txt_update)
            self.btn_add_update = QPushButton("ثبت به‌روزرسانی")
            self.btn_add_update.setCursor(Qt.PointingHandCursor)
            self.btn_add_update.clicked.connect(self.add_update)
            ul.addWidget(self.btn_add_update)
            lay.addWidget(self.update_box)

        self.lbl_timeline_head = self._field_label("تاریخچه‌ی پیشرفت (جدیدترین بالا)")
        lay.addWidget(self.lbl_timeline_head)
        self.timeline = QTextBrowser()
        self.timeline.setObjectName("Timeline")
        self.timeline.setOpenLinks(False)
        self.timeline.setMinimumHeight(110)
        lay.addWidget(self.timeline, 1)

        self._show_detail(None)
        return panel

    @staticmethod
    def _field_label(text):
        lbl = QLabel(text)
        lbl.setObjectName("FieldLabel")
        return lbl

    @staticmethod
    def _body_label():
        lbl = QLabel("")
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return lbl

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
                                                 if (t.is_active and t.can_use_key_activities())
                                                 or t.id in owner_ids])
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
                if col == 0:
                    item.setToolTip(a.title)
                    if a.priority == KEY_PRIORITY_TOP:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                elif col == self._status_col:
                    self._paint_tone(item, STATUS_TONES.get(a.status))
                elif col == self._priority_col and a.priority != KEY_PRIORITY_NORMAL:
                    self._paint_tone(item, PRIORITY_TONES.get(a.priority))
                t.setItem(row, col, item)
            t.setCellWidget(row, self._progress_col, self._progress_cell(a))
        t.blockSignals(False)
        self.lbl_count.setText(f"تعداد کارهای نمایش‌داده‌شده: {len(self.shown)}")
        self._update_empty_state()

    @staticmethod
    def _paint_tone(item, tone):
        if not tone:
            return
        item.setForeground(QColor(tone_color(tone)))
        font = item.font()
        font.setBold(True)
        item.setFont(font)

    @staticmethod
    def _progress_cell(activity):
        """نوار پیشرفتِ باریک با فاصله از لبه‌ی سلول (سلول بی‌رنگ تا انتخاب ردیف دیده شود)."""
        host = _transparent(QWidget())
        lay = QHBoxLayout(host)
        lay.setContentsMargins(10, 0, 10, 0)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(activity.progress or 0)
        bar.setFormat("%p٪")
        bar.setAlignment(Qt.AlignCenter)
        if activity.status == KEY_STATUS_DONE:
            bar.setProperty("state", "done")
        lay.addWidget(bar)
        return host

    def _update_empty_state(self):
        if self.shown:
            self.list_stack.setCurrentWidget(self.table)
            return
        if self.all:
            text = _EMPTY_FILTERED
        else:
            text = _EMPTY_ADMIN if self.admin else _EMPTY_OWNER
        self.lbl_empty.setText(text)
        self.list_stack.setCurrentWidget(self.lbl_empty)

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

    def _on_theme_changed(self, *_):
        self.apply_filters()

    def _show_detail(self, a):
        details = [self.lbl_title, self.chip_row, self.bar_progress, self.lbl_meta,
                   self.lbl_description_head, self.lbl_description,
                   self.lbl_result_head, self.lbl_result,
                   self.lbl_timeline_head, self.timeline]
        if self.update_box is not None:
            details.append(self.update_box)
        selected = a is not None
        self.lbl_placeholder.setVisible(not selected)
        for w in details:
            w.setVisible(selected)
        if not selected:
            # فرمِ غیرفعال و دکمه‌های بی‌کار فقط شلوغی بود؛ کاملاً پنهان می‌شوند
            self.timeline_items = []
            self._set_detail_enabled(False)
            return

        self.lbl_title.setText(a.title)
        self.chip_status.setText(a.status or "-")
        set_tone(self.chip_status, STATUS_TONES.get(a.status, "muted"))
        self.chip_priority.setText(f"اهمیت: {a.priority or '-'}")
        set_tone(self.chip_priority, PRIORITY_TONES.get(a.priority, "muted"))
        self.chip_category.setText(a.category or "بدون دسته")
        set_tone(self.chip_category, "muted")

        self.bar_progress.setValue(a.progress or 0)
        bar_state = "done" if a.status == KEY_STATUS_DONE else ""
        if self.bar_progress.property("state") != bar_state:
            self.bar_progress.setProperty("state", bar_state)
            self.bar_progress.style().unpolish(self.bar_progress)
            self.bar_progress.style().polish(self.bar_progress)

        meta = [f"شروع: {_dt(a.start_date)}", f"اتمام: {_dt(a.end_date)}"]
        if self.admin:
            meta.insert(0, f"ثبت‌کننده: {a.technician_name_snapshot or '-'}")
        self.lbl_meta.setText("   •   ".join(meta))

        self.lbl_description.setText(a.description or "")
        self.lbl_result.setText(a.result or "")
        for head, body in ((self.lbl_description_head, self.lbl_description),
                           (self.lbl_result_head, self.lbl_result)):
            has_text = bool(body.text())
            head.setVisible(has_text)
            body.setVisible(has_text)

        self.timeline_items = svc.timeline(a)
        self.timeline.setHtml(self._timeline_html(self.timeline_items))

        if not self.admin:
            self.spn_update_progress.setValue(a.progress or 0)
            self.cmb_update_status.setCurrentText(a.status or KEY_STATUS_IN_PROGRESS)
            self.date_update.setDate(QDate.currentDate())
            self._set_detail_enabled(True)

    def _timeline_html(self, updates):
        muted = theme.palette["text_muted"]
        if not updates:
            return (f'<p style="color:{muted};">هنوز به‌روزرسانی‌ای ثبت نشده است. '
                    + ("" if self.admin else "از فرم «ثبت پیشرفت جدید» پایین همین پنل "
                       "استفاده کنید.") + "</p>")
        parts = []
        for u in updates:
            progress = f"{u.progress}٪" if u.progress is not None else "-"
            color = tone_color(STATUS_TONES.get(u.status, "muted"))
            parts.append(
                f'<p style="margin:0;"><b>{_dt(u.update_date)}</b>'
                f'&nbsp;&nbsp;<span style="color:{muted};">پیشرفت {progress}</span>'
                f'&nbsp;&nbsp;<span style="color:{color};"><b>{escape(u.status or "-")}</b></span></p>'
                f'<p style="margin:2px 0 12px 0;">{escape(u.text or "")}</p>')
        return "".join(parts)

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

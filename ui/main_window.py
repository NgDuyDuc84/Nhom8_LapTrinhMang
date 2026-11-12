from __future__ import annotations

# Mở trực tiếp file/module cũng đi qua cùng đường khởi động dữ liệu thật.
if __name__ == "__main__":
    import sys
    from pathlib import Path

    if not __package__:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from main import main

    raise SystemExit(main())

from models import now
from html import escape

from PySide6.QtCore import QDateTime, Qt, Slot, QTimer, QTimeZone
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDoubleSpinBox,
    QSpinBox,
    QScrollArea,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.tray import NetGuardTrayIcon
from ui.device_columns import DeviceColumn as Col
from ui.theme import ATTENTION_ROLE, BADGES, LightTable, apply_light_theme, badge_stylesheet

try:
    from pyqtgraph import PlotWidget
except Exception:  # pragma: no cover - fallback nếu môi trường thiếu pyqtgraph
    PlotWidget = QWidget

from backend import BackendBase
from models import Alert, Device, Diagnosis
from extras.device_identity import DEVICE_TYPES, device_title, manufacturer_label, type_label


class DeviceDialog(QDialog):
    """Hộp thoại sửa tên và ghi chú thiết bị."""

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self.device = device
        self.setWindowTitle("Chi tiết và nhận diện thiết bị")
        self.resize(640, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(device.name or "")
        self.name_edit.setPlaceholderText(device_title(device))
        self.note_edit = QLineEdit(device.note or "")
        self.type_combo = QComboBox()
        self.type_combo.addItem("Tự nhận diện", "")
        for kind, label in DEVICE_TYPES.items():
            if kind != "unknown":
                self.type_combo.addItem(label, kind)
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(device.type_override)))
        form.addRow("Tên gợi nhớ:", self.name_edit)
        form.addRow("Ghi chú:", self.note_edit)
        form.addRow("Xác nhận loại thiết bị:", self.type_combo)
        for label, value in (
            ("Tên phát hiện:", device.discovered_name or device.hostname or "Chưa có"),
            ("Địa chỉ MAC:", device.mac), ("Địa chỉ IP:", device.ip),
            ("Hãng / linh kiện mạng:", manufacturer_label(device)),
            ("Hãng đăng ký MAC:", device.vendor if device.vendor != "Unknown" else "Chưa xác định"),
            ("Model tự công bố:", device.model or "Chưa có"),
            ("Loại tự nhận diện:", type_label(device, automatic=True)),
            ("Thông tin LAN cập nhật:", device.identity_seen.strftime("%d/%m/%Y %H:%M:%S")
             if device.identity_seen else "Chưa có phản hồi tên/dịch vụ"),
        ):
            text = QLabel(value)
            text.setTextFormat(Qt.PlainText)
            text.setWordWrap(True)
            text.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(label, text)
        layout.addLayout(form)
        evidence = QLabel(device.identity_evidence or "Chưa đủ thông tin nhận diện. Bấm Làm mới mạng để thử lại.")
        evidence.setTextFormat(Qt.PlainText)
        evidence.setWordWrap(True)
        evidence.setStyleSheet("color: #64748B; padding: 8px 0;")
        layout.addWidget(evidence)
        explanation = QLabel("Thông tin tự công bố chỉ là gợi ý. Bạn có thể xác nhận loại thiết bị ở trên.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Lưu")
        save_btn.setProperty("primary", True)
        cancel_btn = QPushButton("Huỷ")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def values(self):
        return self.name_edit.text(), self.note_edit.text()

    def type_override(self) -> str:
        return self.type_combo.currentData()


class MainWindow(QMainWindow):
    """Cửa sổ chính của NetGuard, tích hợp các màn hình monitor và báo cáo."""

    def __init__(self, backend: BackendBase, *, warnings: list[str] | None = None):
        super().__init__()
        self.backend = backend
        apply_light_theme(QApplication.instance())
        self._device_rows: dict[str, int] = {}
        self._refreshing = False
        self._device_cache = {}
        self._device_offset = 0
        self._device_page_size = 250
        self._device_timer = QTimer(self)
        self._device_timer.setSingleShot(True)
        self._device_timer.timeout.connect(self.refresh_devices)
        self._diagnosis_timer = QTimer(self)
        self._diagnosis_timer.setSingleShot(True)
        self._diagnosis_timer.timeout.connect(self.refresh_diagnosis)
        self._network_refresh_running = False
        self._network_refresh_request_id = 0
        self._latest_diagnosis = backend.get_latest_diagnosis()
        self._measurements = backend.get_latest_measurements()

        self.setWindowTitle("NetGuard - Giám sát mạng LAN")
        self.resize(1280, 840)

        self.toolbar = self.addToolBar("NetGuard")
        self.toolbar.setMovable(False)
        brand = QLabel("NetGuard")
        brand.setObjectName("brand")
        self.toolbar.addWidget(brand)
        toolbar_spacer = QWidget()
        toolbar_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(toolbar_spacer)

        self.refresh_action = QPushButton("Làm mới mạng")
        self.refresh_action.setToolTip("Đọc lại kết nối và đo mới. Với mạng lớn, quét phần kế tiếp; xem tiến độ phủ subnet bên dưới.")
        self.refresh_action.clicked.connect(self.request_network_refresh)
        self.toolbar.addWidget(self.refresh_action)

        self.trust_action = QPushButton("Tin cậy")
        self.trust_action.clicked.connect(self.toggle_selected_trust)
        self.toolbar.addWidget(self.trust_action)

        self.trust_all_action = QPushButton("Tin cậy tất cả")
        self.trust_all_action.clicked.connect(self.trust_all_devices)
        self.toolbar.addWidget(self.trust_all_action)

        self.rename_action = QPushButton("Chi tiết / Sửa tên")
        self.rename_action.clicked.connect(self.rename_selected_device)
        self.toolbar.addWidget(self.rename_action)

        self.report_action = QPushButton("Xuất báo cáo")
        self.report_action.setProperty("primary", True)
        self.report_action.clicked.connect(self.export_report)
        self.toolbar.addWidget(self.report_action)

        self.tray = NetGuardTrayIcon(self)
        self.tray.show()
        self.tray.notify("NetGuard", "Ứng dụng đang chạy nền.", "info")

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(12)
        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(4)
        page_title = QLabel("Tổng quan mạng")
        page_title.setObjectName("pageTitle")
        subtitle = QLabel("Theo dõi thiết bị, kết nối và cảnh báo trong mạng LAN")
        subtitle.setObjectName("subtitle")
        title_group.addWidget(page_title)
        title_group.addWidget(subtitle)
        header.addLayout(title_group)
        header.addStretch()
        main_layout.addLayout(header)
        self.connection_label = QLabel()
        self.connection_label.setObjectName("connection")
        self.connection_label.setTextFormat(Qt.RichText)
        self.connection_label.setWordWrap(True)
        main_layout.addWidget(self.connection_label)
        self.refresh_status_label = QLabel()
        self.refresh_status_label.setTextFormat(Qt.PlainText)
        self.refresh_status_label.setWordWrap(True)
        self.refresh_status_label.hide()
        main_layout.addWidget(self.refresh_status_label)
        self.scan_progress_label = QLabel()
        self.scan_progress_label.setTextFormat(Qt.PlainText)
        self.scan_progress_label.setWordWrap(True)
        self.scan_progress_label.hide()
        main_layout.addWidget(self.scan_progress_label)
        self.environment_label = QLabel("\n".join(warnings or []))
        self.environment_label.setObjectName("environment")
        self.environment_label.setTextFormat(Qt.PlainText)
        self.environment_label.setWordWrap(True)
        self.environment_label.setVisible(bool(warnings))
        main_layout.addWidget(self.environment_label)
        self._stat_values = {}
        statistics = QHBoxLayout()
        statistics.setSpacing(16)
        for key, label, color in (
            ("total", "Tổng thiết bị đã biết", "#2563EB"),
            ("online", "Đang online", "#15803D"),
            ("pending", "Chưa xác minh", "#B45309"),
            ("untrusted", "Chưa tin cậy", "#C2410C"),
        ):
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 12, 18, 12)
            card_layout.setSpacing(6)
            caption = QLabel(f'<span style="color:{color}">●</span>  {label}')
            caption.setObjectName("statCaption")
            value = QLabel("0")
            value.setObjectName("statValue")
            self._stat_values[key] = value
            card_layout.addWidget(caption)
            card_layout.addWidget(value)
            shadow = QGraphicsDropShadowEffect(card)
            shadow.setBlurRadius(6)
            shadow.setOffset(0, 1)
            shadow.setColor(QColor(15, 23, 42, 15))
            card.setGraphicsEffect(shadow)
            statistics.addWidget(card)
        main_layout.addLayout(statistics)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.devices_tab = QWidget()
        self.alerts_tab = QWidget()
        self.diagnosis_tab = QWidget()
        self.report_tab = QWidget()

        self.tabs.addTab(self.devices_tab, "Thiết bị")
        self.tabs.addTab(self.alerts_tab, "Cảnh báo")
        self.tabs.addTab(self.diagnosis_tab, "Chẩn đoán")
        self.tabs.addTab(self.report_tab, "Báo cáo")

        self._init_devices_tab()
        self._init_alerts_tab()
        self._init_diagnosis_tab()
        self._init_report_tab()

        self._connect_backend_signals()
        self.on_connection_changed(backend.get_connection_status())
        self._latest_diagnosis = backend.get_latest_diagnosis()
        self._measurements = backend.get_latest_measurements()
        self.refresh_devices()
        self.refresh_alerts()
        self.refresh_diagnosis()
        self.on_network_refresh_changed(backend.get_refresh_status())
        self.on_scan_progress_changed(backend.get_scan_progress())

    def _connect_backend_signals(self) -> None:
        self.backend.device_updated.connect(self.on_device_updated)
        self.backend.alert_raised.connect(self.on_alert_raised)
        self.backend.diagnosis_changed.connect(self.on_diagnosis_changed)
        self.backend.ping_result.connect(self.on_ping_result)
        self.backend.connection_changed.connect(self.on_connection_changed)
        self.backend.measurement_changed.connect(self.on_measurement_changed)
        self.backend.devices_refreshed.connect(self.schedule_devices)
        self.backend.network_refresh_changed.connect(self.on_network_refresh_changed)
        self.backend.scan_progress_changed.connect(self.on_scan_progress_changed)
        self.backend.service_status_changed.connect(self.on_service_status)
        self.backend.report_finished.connect(self.on_report_finished)
        self.backend.utility_finished.connect(self.report_text.setPlainText)
        self.backend.traceroute_done.connect(lambda hops: self.report_text.setPlainText("Traceroute (hop quan sát, chưa xác minh ISP):\n" + "\n".join(f"{h.ttl}: {h.ip or '*'} - {h.rtt_ms if h.rtt_ms is not None else 'N/A'} ms" for h in hops)))

    @Slot()
    def request_network_refresh(self) -> None:
        try:
            self.backend.refresh_network()
            self.on_network_refresh_changed(self.backend.get_refresh_status())
        except Exception as exc:
            self.on_network_refresh_changed({
                "running": False,
                "message": f"Không thể làm mới mạng: {exc}",
                "errors": [str(exc)],
            })

    @Slot(object)
    def on_network_refresh_changed(self, status: dict) -> None:
        request_id = status.get("request_id", self._network_refresh_request_id)
        if request_id < self._network_refresh_request_id:
            return  # Qt có thể còn đang giao signal của lượt làm mới trước.
        self._network_refresh_request_id = request_id
        running = bool(status.get("running"))
        began = running and not self._network_refresh_running
        self._network_refresh_running = running
        self.refresh_action.setEnabled(not running)
        self.refresh_action.setText("Đang làm mới…" if running else "Làm mới mạng")
        message = status.get("message", "")
        self.refresh_status_label.setText(message)
        self.refresh_status_label.setVisible(bool(message))
        tone = "pending" if running else "danger" if status.get("errors") else "success"
        self.refresh_status_label.setStyleSheet(badge_stylesheet(tone))
        if not running and hasattr(self, "device_table"):
            self.refresh_devices()
        if began:
            self._latest_diagnosis = None
            self._measurements = {}
            self.refresh_devices()
            self.refresh_diagnosis()

    def _init_devices_tab(self) -> None:
        layout = QVBoxLayout(self.devices_tab)
        layout.setContentsMargins(0, 12, 0, 0)
        options = QHBoxLayout()
        hint = QLabel("Loại có chữ “gợi ý” chưa được xác nhận. Chọn thiết bị để xem Chi tiết / Sửa tên.")
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        options.addWidget(hint, 1)
        self.show_network_details = QCheckBox("Hiện MAC / IP")
        self.show_network_details.toggled.connect(self._toggle_network_columns)
        options.addWidget(self.show_network_details)
        tools = QPushButton("Công cụ")
        menu = QMenu(tools)
        for title, handler in (("Hoàn tất thiết lập / Bật cảnh báo", self.finish_setup),
                               ("Xác nhận MAC router đã chọn", self.accept_gateway),
                               ("Traceroute", self.trace_route), ("Lịch sử thiết bị đã chọn", self.show_presence),
                               ("Xuất danh sách CSV", self.export_csv), ("Quét kênh Wi-Fi", self.show_wifi),
                               ("Cài đặt", self.show_settings), ("Sao lưu CSDL mạng hiện tại", self.backup_database),
                               ("Khôi phục CSDL mạng hiện tại", self.restore_database),
                               ("Xem hồ sơ mạng / lịch sử cũ", self.select_history)):
            menu.addAction(title, handler)
        tools.setMenu(menu)
        options.addWidget(tools)
        layout.addLayout(options)
        self.baseline_label = QLabel()
        self.baseline_label.setWordWrap(True)
        layout.addWidget(self.baseline_label)
        self.device_table = LightTable()
        self.device_table.setObjectName("deviceTable")
        self.device_table.setColumnCount(len(Col))
        self.device_table.setHorizontalHeaderLabels([
            "THIẾT BỊ", "LOẠI THIẾT BỊ", "NHÀ SẢN XUẤT", "TRẠNG THÁI", "TIN CẬY",
            "THẤY GẦN NHẤT", "GHI CHÚ", "ĐỊA CHỈ MAC", "ĐỊA CHỈ IP",
        ])
        self.device_table.setAlternatingRowColors(True)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.device_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.device_table.cellChanged.connect(self._handle_device_cell_edit)
        self.device_table.itemChanged.connect(self._handle_device_item_changed)
        self._toggle_network_columns(False)
        layout.addWidget(self.device_table)
        pages = QHBoxLayout()
        self.device_page_label = QLabel()
        pages.addWidget(self.device_page_label, 1)
        self.device_previous = QPushButton("Trang trước")
        self.device_next = QPushButton("Trang sau")
        self.device_previous.clicked.connect(lambda: self.change_device_page(-1))
        self.device_next.clicked.connect(lambda: self.change_device_page(1))
        pages.addWidget(self.device_previous)
        pages.addWidget(self.device_next)
        layout.addLayout(pages)

    def change_device_page(self, direction):
        if self.device_table.state() == QAbstractItemView.EditingState:
            self.device_table.setFocus()  # Chốt editor trước khi đổi trang.
        self._device_offset = max(0, self._device_offset + direction * self._device_page_size)
        self.refresh_devices()

    def _toggle_network_columns(self, visible: bool) -> None:
        for column in (Col.MAC, Col.IP):
            self.device_table.setColumnHidden(column, not visible)

    def _init_alerts_tab(self) -> None:
        layout = QVBoxLayout(self.alerts_tab)
        layout.setContentsMargins(0, 12, 0, 0)
        self.alert_banner = QLabel("Chưa có cảnh báo mới.")
        self.alert_banner.setWordWrap(True)
        self.alert_banner.setStyleSheet(badge_stylesheet("success"))
        layout.addWidget(self.alert_banner)
        filters = QHBoxLayout()
        self.alert_search = QLineEdit()
        self.alert_search.setPlaceholderText("Tìm cảnh báo")
        self.alert_search.returnPressed.connect(lambda: self.change_alert_page(0, reset=True))
        filters.addWidget(self.alert_search)
        for label, callback in (("Trước", lambda: self.change_alert_page(-100)), ("Sau", lambda: self.change_alert_page(100)),
                                ("Đánh dấu đã xử lý", self.acknowledge_selected_alert)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            filters.addWidget(button)
        self._alert_offset = 0
        layout.addLayout(filters)
        self.alert_list = QListWidget()
        self.alert_list.setWordWrap(True)
        self.alert_list.setSpacing(4)
        layout.addWidget(self.alert_list)

    def _init_diagnosis_tab(self) -> None:
        outer = QVBoxLayout(self.diagnosis_tab)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        contents = QWidget()
        scroll.setWidget(contents)
        outer.addWidget(scroll)
        layout = QVBoxLayout(contents)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)
        top = QHBoxLayout()
        self.verdict_label = QLabel("Đang chờ dữ liệu...")
        self.verdict_label.setStyleSheet(badge_stylesheet("pending", large=True))
        top.addWidget(self.verdict_label, 0, Qt.AlignLeft)
        top.addStretch()
        layout.addLayout(top)

        self.diagnosis_text = QLabel("Chưa có kết quả chẩn đoán.")
        self.diagnosis_text.setWordWrap(True)
        self.diagnosis_text.setStyleSheet("font-size: 14px; color: #475569; padding: 2px;")
        layout.addWidget(self.diagnosis_text)

        self.measurement_table = LightTable(3, 5)
        self.measurement_table.setHorizontalHeaderLabels([
            "MỐC", "ĐỊA CHỈ ĐÍCH", "RTT GẦN NHẤT", "MẤT GÓI (30 MẪU LỊCH SỬ)", "TRẠNG THÁI MẪU MỚI",
        ])
        self.measurement_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.measurement_table.setFixedHeight(190)
        self.measurement_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.measurement_table)
        history_caption = QLabel("Lịch sử RTT trong 30 phút · Khoảng trống là mẫu không có phản hồi")
        history_caption.setObjectName("subtitle")
        layout.addWidget(history_caption)

        self.diagnosis_plot = PlotWidget()
        self.diagnosis_plot.setFixedHeight(210)
        if PlotWidget is not QWidget:
            self.diagnosis_plot.setBackground("#FFFFFF")
            for axis in ("left", "bottom"):
                self.diagnosis_plot.getAxis(axis).setPen("#E3E8F0")
                self.diagnosis_plot.getAxis(axis).setTextPen("#64748B")
        layout.addWidget(self.diagnosis_plot)
        self.loss_plot = PlotWidget()
        self.loss_plot.setFixedHeight(155)
        layout.addWidget(self.loss_plot)
        self._curves, self._loss_curves = {}, {}
        if PlotWidget is not QWidget:
            self.diagnosis_plot.addLegend(colCount=3, offset=(10, 5), labelTextColor="#475569", brush=(255, 255, 255, 230))
            self.loss_plot.setBackground("#FFFFFF")
            self.loss_plot.setLabel("left", "Mất gói", units="%")
            self.loss_plot.setYRange(0, 100)
            self.loss_plot.addLegend(colCount=3, offset=(10, 5), labelTextColor="#475569", brush=(255, 255, 255, 230))
            for target, label, color in (("router", "Router", "#2563EB"), ("isp", "Hop sau gateway", "#C2410C"), ("external", "Đích ngoài", "#15803D")):
                self._curves[target] = self.diagnosis_plot.plot([], [], pen=color, name=label, connect="finite")
                self._loss_curves[target] = self.loss_plot.plot([], [], pen=color, name=label, connect="finite")

    def _init_report_tab(self) -> None:
        layout = QVBoxLayout(self.report_tab)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(16)
        form = QFormLayout()
        initial = QDateTime.fromString(now().isoformat(timespec="seconds") + "+07:00", Qt.ISODate)
        self.start_time = QDateTimeEdit(initial.addSecs(-3600))
        self.end_time = QDateTimeEdit(initial)
        for editor in (self.start_time, self.end_time):
            editor.setTimeZone(QTimeZone(7*3600))
        self.start_time.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.end_time.setDisplayFormat("dd/MM/yyyy HH:mm")
        form.addRow("Từ (GMT+7):", self.start_time)
        form.addRow("Đến (GMT+7):", self.end_time)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.export_btn = QPushButton("Xuất báo cáo PDF")
        self.export_btn.setProperty("primary", True)
        self.export_btn.clicked.connect(self.export_report)
        buttons.addStretch()
        buttons.addWidget(self.export_btn)
        self.cancel_export_btn = QPushButton("Hủy xuất")
        self.cancel_export_btn.setEnabled(False)
        self.cancel_export_btn.clicked.connect(lambda: self.backend.cancel_report())
        buttons.addWidget(self.cancel_export_btn)
        layout.addLayout(buttons)

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlaceholderText("Kết quả xuất báo cáo sẽ hiện ở đây.")
        layout.addWidget(self.report_text)

    def schedule_devices(self):
        if not self._device_timer.isActive():
            self._device_timer.start(75)

    def refresh_devices(self) -> None:
        if self.device_table.state() == QAbstractItemView.EditingState:
            self._device_timer.start(250)
            return
        try:
            devices = self.backend.list_devices()
            statuses = [self.backend.get_device_status(device) for device in devices]
        except Exception as exc:
            self.statusBar().showMessage(f"Không tải được thiết bị: {exc}", 15000)
            return
        self._display_connection = self.backend.get_connection_status()
        self._refreshing = True
        self.device_table.setUpdatesEnabled(False)
        try:
            self._device_cache = {d.mac: d for d in devices}
            self._device_offset = min(self._device_offset, max(0, (len(devices)-1)//self._device_page_size)*self._device_page_size)
            start, end = self._device_offset, self._device_offset + self._device_page_size
            page_devices, page_statuses = devices[start:end], statuses[start:end]
            page_macs = {device.mac for device in page_devices}
            self.device_page_label.setText(f"Hiện {start+1 if devices else 0}–{min(end, len(devices))} / {len(devices)} thiết bị đã biết")
            self.device_previous.setEnabled(start > 0)
            self.device_next.setEnabled(end < len(devices))
            for row in reversed(range(self.device_table.rowCount())):
                mac_item = self.device_table.item(row, Col.MAC)
                if mac_item and mac_item.text() not in page_macs:
                    self.device_table.removeRow(row)
            self._device_rows = {self.device_table.item(r, Col.MAC).text(): r for r in range(self.device_table.rowCount())}
            for key, value in {"total": len(devices), "online": statuses.count("Online"),
                               "pending": sum(v.startswith("Chưa xác minh") for v in statuses),
                               "untrusted": sum(not d.trusted for d in devices)}.items():
                self._stat_values[key].setText(str(value))
            for device, status in zip(page_devices, page_statuses):
                row = self._device_rows.get(device.mac)
                if row is None:
                    row = self.device_table.rowCount()
                    self.device_table.insertRow(row)
                    self._device_rows[device.mac] = row
                values = [device_title(device), type_label(device), manufacturer_label(device), status, "",
                          device.last_seen.strftime("%d/%m %H:%M:%S"), device.note or "", device.mac, device.ip]
                for column, value in enumerate(values):
                    item = self.device_table.item(row, column)
                    if item is None:
                        item = QTableWidgetItem()
                        if column not in (Col.NAME, Col.NOTE, Col.TRUSTED):
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        if column == Col.TRUSTED:
                            item.setFlags((item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
                        self.device_table.setItem(row, column, item)
                    if item.text() != str(value):
                        item.setText(str(value))
                    item.setData(Qt.UserRole, device.mac)
                    item.setToolTip(device.identity_evidence if column in (Col.TYPE, Col.MANUFACTURER) else str(value))
                    if column == Col.NAME:
                        item.setData(ATTENTION_ROLE, "warning" if not device.trusted else None)
                        item.setToolTip(f"{value}\nMAC: {device.mac}\nIP: {device.ip}")
                    if column == Col.TRUSTED:
                        state = Qt.Checked if device.trusted else Qt.Unchecked
                        if item.checkState() != state:
                            item.setCheckState(state)
            for column, width in ((Col.NAME, 220), (Col.TYPE, 210), (Col.MANUFACTURER, 205),
                                  (Col.STATUS, 200), (Col.LAST_SEEN, 150), (Col.NOTE, 120), (Col.MAC, 176)):
                self.device_table.setColumnWidth(column, width)
            self.device_table.horizontalHeader().setStretchLastSection(True)
            try:
                first = self.backend.is_first_run()
                self.baseline_label.setText("Chưa bật cảnh báo thiết bị chưa tin cậy. Kiểm tra danh sách, sau đó chọn Công cụ → Hoàn tất thiết lập." if first else "Đã bật cảnh báo thiết bị chưa tin cậy cho hồ sơ mạng này. MAC/ARP là thông tin quan sát, không xác thực danh tính.")
            except Exception as exc:
                self.baseline_label.setText(f"Chưa đọc được trạng thái thiết lập: {exc}")
        finally:
            self._refreshing = False
            self.device_table.setUpdatesEnabled(True)

    def refresh_alerts(self) -> None:
        alerts = self.backend.get_alerts(limit=100, offset=self._alert_offset, query=self.alert_search.text())
        self.alert_list.clear()
        if not alerts:
            self.alert_banner.setText("Chưa có cảnh báo được ghi nhận; trạng thái mạng xem ở tab Chẩn đoán.")
            self.alert_banner.setStyleSheet(badge_stylesheet("success"))
            return

        self.alert_banner.setText(f"Có {len(alerts)} cảnh báo gần nhất.")
        self.alert_banner.setStyleSheet(badge_stylesheet(
            "danger" if any(alert.level == "danger" for alert in alerts) else "warning"
        ))

        for alert in alerts:
            item = QListWidgetItem(f"{alert.level.upper()}  ·  {alert.ts:%d/%m %H:%M:%S}\n{alert.message}")
            item.setData(Qt.UserRole, alert.id)
            if alert.acknowledged:
                item.setText("[Đã xử lý] " + item.text())
            tone = "danger" if alert.level == "danger" else "warning" if alert.level == "warning" else "success"
            background, foreground = BADGES[tone]
            item.setForeground(QColor(foreground))
            item.setBackground(QColor(background))
            self.alert_list.addItem(item)

    def change_alert_page(self, delta, reset=False):
        self._alert_offset = 0 if reset else max(0, self._alert_offset+delta)
        self.refresh_alerts()

    def acknowledge_selected_alert(self):
        item = self.alert_list.currentItem()
        if item and item.data(Qt.UserRole):
            try:
                self.backend.acknowledge_alert(item.data(Qt.UserRole))
                self.refresh_alerts()
            except Exception as exc:
                QMessageBox.warning(self, "Cảnh báo", str(exc))

    def refresh_diagnosis(self) -> None:
        history = {
            "router": self.backend.get_ping_history("router", 30),
            "isp": self.backend.get_ping_history("isp", 30),
            "external": self.backend.get_ping_history("external", 30),
        }
        latest = self._latest_diagnosis
        verdict = latest.verdict if latest else "unknown"
        self.verdict_label.setText(verdict if latest else "Đang chờ phép đo")
        tone = "success" if verdict == "ok" else (
            "danger" if verdict in {"home_issue", "isp_issue", "internet_issue"} else "pending"
        )
        self.verdict_label.setStyleSheet(badge_stylesheet(tone, large=True))
        self.diagnosis_text.setText(latest.text if latest else
                                    "Chưa có kết luận từ bộ chẩn đoán trong phiên hiện tại.")

        results = self._measurements.get("results", {})
        statuses = self._measurements.get("status", {})
        addresses = self._measurements.get("addresses", {})
        for row, (target, label) in enumerate((("router", "Router"), ("isp", "Hop sau gateway"), ("external", "Internet"))):
            result = results.get(target)
            samples = [s for s in history[target] if s.status in {"ok", "timeout"} and (not addresses.get(target) or s.address == addresses.get(target) or not s.address)][-30:]
            loss = sum(sample.loss_pct for sample in samples) / len(samples) if samples else None
            rtt = f"{result.rtt_ms:.2f} ms" if result and result.rtt_ms is not None else "—"
            status = statuses.get(target, "Chưa đo trong phiên")
            if result:
                status = ("Có phản hồi" if result.rtt_ms is not None else "Không có phản hồi") + f" lúc {result.ts:%H:%M:%S}"
            values = [label, addresses.get(target) or "—", rtt,
                      f"{loss:.1f}%" if loss is not None else "—", status]
            for column, value in enumerate(values):
                self.measurement_table.setItem(row, column, QTableWidgetItem(value))
        self.measurement_table.resizeColumnsToContents()

        if PlotWidget is QWidget:
            self.diagnosis_plot.setVisible(False)
            self.loss_plot.setVisible(False)
            return

        self.diagnosis_plot.showGrid(True, True, alpha=0.15)
        self.diagnosis_plot.setLabel("left", "RTT", units="ms", color="#64748B")
        self.diagnosis_plot.setLabel("bottom", "Thời gian so với hiện tại", units="s", color="#64748B")

        for target, label, color in [
            ("router", "Router", "#2563EB"),
            ("isp", "Hop sau gateway", "#C2410C"),
            ("external", "Internet", "#15803D"),
        ]:
            samples = history.get(target, [])
            if not samples:
                self._curves[target].setData([], [])
                self._loss_curves[target].setData([], [])
                continue
            stamp = now()
            x = [(sample.ts - stamp).total_seconds() for sample in samples]
            y = [sample.rtt_ms if sample.rtt_ms is not None else float("nan") for sample in samples]
            # Chèn khoảng trống nếu không có mẫu hoặc đổi phiên/địa chỉ.
            xx, yy, loss_y = [], [], []
            previous = None
            for sample, px, py in zip(samples, x, y):
                if previous and ((sample.ts-previous.ts).total_seconds() > 10 or sample.session_id != previous.session_id or sample.address != previous.address):
                    xx.append(px-.001); yy.append(float("nan")); loss_y.append(float("nan"))
                xx.append(px); yy.append(py if sample.status in {"ok", "timeout"} else float("nan"))
                loss_y.append(sample.loss_pct if sample.status in {"ok", "timeout"} else float("nan"))
                previous = sample
            self._curves[target].setData(xx, yy, connect="finite")
            self._loss_curves[target].setData(xx, loss_y, connect="finite")

    @Slot(object)
    def on_connection_changed(self, status: dict) -> None:
        current = self.backend.get_connection_status()
        if any(current.get(key, False if key == "connected" else "") != value for key, value in status.items()):
            return
        self._measurements = {}
        self._latest_diagnosis = None
        self._device_offset = 0
        self.on_scan_progress_changed(self.backend.get_scan_progress())
        if status.get("connected"):
            self.connection_label.setText(
                f"Card: <b style='color:#1E293B'>{escape(status['name'])}</b> &nbsp; · &nbsp; "
                f"IPv4: <b style='color:#1E293B'>{escape(status['ip'])}/{escape(status['netmask'])}</b>"
                f" &nbsp; · &nbsp; Gateway: <b style='color:#1E293B'>{escape(status['gateway'] or 'chưa có')}</b>"
            )
        else:
            self.connection_label.setText("Chưa có kết nối LAN hợp lệ; đang chờ kết nối.")
        if hasattr(self, "diagnosis_plot"):
            self.refresh_diagnosis()
            self.refresh_devices()

    @Slot(object)
    def on_measurement_changed(self, measurements: dict) -> None:
        if self.backend.get_latest_measurements() != measurements:
            return
        self._measurements = measurements
        self.refresh_diagnosis()

    @Slot(object)
    def on_device_updated(self, device: Device) -> None:
        self.schedule_devices()

    @Slot(object)
    def on_alert_raised(self, alert: Alert) -> None:
        if alert.network_id and alert.network_id != getattr(self.backend, "_storage_network", alert.network_id):
            return
        self.refresh_alerts()
        if self.tray is not None:
            self.tray.notify("Cảnh báo NetGuard", alert.message, alert.level)

    @Slot(object)
    def on_diagnosis_changed(self, diagnosis: Diagnosis) -> None:
        if self.backend.get_latest_diagnosis() != diagnosis:
            return
        self._latest_diagnosis = diagnosis
        if not self._diagnosis_timer.isActive():
            self._diagnosis_timer.start(75)

    @Slot(object)
    def on_ping_result(self, result) -> None:
        pass  # measurement_changed giao một snapshot cho cả chu kỳ.

    def _can_edit_displayed(self):
        if getattr(self, "_display_connection", None) != self.backend.get_connection_status():
            self.statusBar().showMessage("Kết nối đã đổi; chọn lại thiết bị sau khi bảng cập nhật. Chưa lưu vào hồ sơ mới.", 15000)
            self.schedule_devices()
            return False
        return True

    def _handle_device_item_changed(self, item):
        if self._refreshing or item is None:
            return
        if item.column() != Col.TRUSTED:
            return
        if not self._can_edit_displayed():
            return
        checked = item.checkState() == Qt.Checked
        mac = item.data(Qt.UserRole)
        if mac:
            try:
                self.backend.set_trusted(mac, checked)
            except Exception as exc:
                self.statusBar().showMessage(f"Không lưu được tin cậy: {exc}", 15000)
                self.schedule_devices()

    def _handle_device_cell_edit(self, row, col):
        if self._refreshing:
            return
        if col not in (Col.NAME, Col.NOTE):
            return
        if not self._can_edit_displayed():
            return
        item = self.device_table.item(row, col)
        if item is None:
            return
        device = self._row_to_device(row)
        if device is None:
            return
        name = self.device_table.item(row, Col.NAME).text().strip() if col == Col.NAME else device.name
        note = self.device_table.item(row, Col.NOTE).text().strip() if self.device_table.item(row, Col.NOTE) else ""
        try:
            self.backend.rename(device.mac, name, note)
        except Exception as exc:
            self.statusBar().showMessage(f"Không lưu được thiết bị: {exc}", 15000)
            self.schedule_devices()

    def _row_to_device(self, row_index: int) -> Device | None:
        item = self.device_table.item(row_index, Col.MAC)
        return self._device_cache.get(item.text()) if item else None

    def trust_all_devices(self) -> None:
        if not self._can_edit_displayed():
            return
        try:
            for device in self.backend.list_devices():
                if not device.trusted:
                    self.backend.set_trusted(device.mac, True)
        except Exception as exc:
            QMessageBox.warning(self, "Không lưu được tin cậy", str(exc))
        self.schedule_devices()

    def toggle_selected_trust(self) -> None:
        if not self._can_edit_displayed():
            return
        selected_rows = sorted({index.row() for index in self.device_table.selectedIndexes()})
        if not selected_rows:
            return
        try:
            for row in selected_rows:
                device = self._row_to_device(row)
                if device is not None:
                    self.backend.set_trusted(device.mac, not device.trusted)
        except Exception as exc:
            QMessageBox.warning(self, "Không lưu được tin cậy", str(exc))

    def rename_selected_device(self) -> None:
        if not self._can_edit_displayed():
            return
        row = self.device_table.currentRow()
        if row < 0:
            return
        device = self._row_to_device(row)
        if device is None:
            return
        displayed_connection = self.backend.get_connection_status()
        dialog = DeviceDialog(device, self)
        if dialog.exec() == QDialog.Accepted:
            if self.backend.get_connection_status() != displayed_connection:
                QMessageBox.warning(self, "Thiết bị", "Kết nối đã đổi trong khi mở chi tiết; chọn lại thiết bị ở mạng hiện tại.")
                return
            name, note = dialog.values()
            try:
                self.backend.rename(device.mac, name, note)
                self.backend.set_device_type(device.mac, dialog.type_override())
            except Exception as exc:
                QMessageBox.critical(self, "Không lưu được thiết bị", str(exc))

    def export_report(self) -> None:
        start = self.start_time.dateTime().toPython()
        end = self.end_time.dateTime().toPython()
        if end < start:
            QMessageBox.warning(self, "Báo cáo", "Thời gian kết thúc phải sau thời gian bắt đầu.")
            return

        default_path = "netguard_report.pdf"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu báo cáo PDF", default_path, "PDF Files (*.pdf)",
            options=QFileDialog.DontUseNativeDialog,
        )
        if not save_path:
            return
        try:
            self.backend.export_report_async(start, end, save_path)
            self.export_btn.setEnabled(False)
            self.report_action.setEnabled(False)
            self.cancel_export_btn.setEnabled(True)
            self.report_text.setPlainText("Đang tổng hợp dữ liệu và dựng PDF ở nền…")
        except Exception as exc:  # pragma: no cover - UI-level handling
            QMessageBox.critical(self, "Lỗi xuất báo cáo", str(exc))

    @Slot(object)
    def on_scan_progress_changed(self, progress):
        if progress != self.backend.get_scan_progress():
            return
        if not progress:
            self.scan_progress_label.hide()
            return
        total, completed = progress["total_hosts"], progress["completed_hosts"]
        def number(value):
            return f"{value:,}".replace(",", ".")
        text = f"Dải {progress['network']}: đã kiểm tra {number(completed)}/{number(total)} địa chỉ trong vòng quét ({completed/total:.1%})."
        if total > progress["batch_hosts"]:
            text += " Thiết bị được bổ sung dần; chỉ địa chỉ đã quét mới được tính vắng mặt."
        self.scan_progress_label.setText(text)
        self.scan_progress_label.show()

    @Slot(object)
    def on_service_status(self, status):
        if status.get("error"):
            self.statusBar().showMessage(f"{status['service']}: {status['error']} - dữ liệu có thể đã cũ.", 20000)
        elif status.get("running"):
            self.statusBar().showMessage(f"{status['service']}: đang hoạt động", 3000)

    @Slot(object)
    def on_report_finished(self, result):
        self.export_btn.setEnabled(True)
        self.report_action.setEnabled(True)
        self.cancel_export_btn.setEnabled(False)
        self.report_text.setPlainText(f"Xuất PDF thành công:\n{result['path']}" if result.get("ok") else f"Xuất PDF chưa hoàn tất: {result.get('error', '')}")

    def finish_setup(self):
        devices = self.backend.list_devices()
        if not devices:
            QMessageBox.information(self, "Thiết lập", "Hãy làm mới mạng và kiểm tra danh sách trước.")
            return
        if QMessageBox.question(self, "Bật cảnh báo", f"Đã kiểm tra {len(devices)} thiết bị của mạng hiện tại? Các thiết bị chưa được đánh dấu Tin cậy sẽ được cảnh báo, kể cả thiết bị đã có trong danh sách. MAC không xác thực danh tính.") != QMessageBox.Yes:
            return
        try:
            self.backend.finish_baseline()
            self.refresh_devices()
        except Exception as exc:
            QMessageBox.critical(self, "Thiết lập", str(exc))

    def accept_gateway(self):
        device = self._row_to_device(self.device_table.currentRow())
        if device and QMessageBox.question(self, "Xác nhận router", f"Bạn đã kiểm tra router thực tế và xác nhận MAC {device.mac}? Thay đổi này cập nhật mốc so sánh gateway của mạng hiện tại.") == QMessageBox.Yes:
            try:
                self.backend.accept_gateway(device.mac)
            except Exception as exc:
                QMessageBox.critical(self, "Router", str(exc))

    def trace_route(self):
        try:
            self.backend.run_traceroute()
            self.tabs.setCurrentWidget(self.report_tab)
            self.report_text.setPlainText("Đang traceroute trong nền…")
        except Exception as exc:
            QMessageBox.warning(self, "Traceroute", str(exc))

    def show_presence(self):
        device = self._row_to_device(self.device_table.currentRow())
        if device:
            rows = self.backend.get_device_history(device.mac, 24)
            self.tabs.setCurrentWidget(self.report_tab)
            self.report_text.setPlainText("Lịch sử quan sát 24 giờ (không xác thực thiết bị; không suy diễn qua khoảng ứng dụng ngừng chạy):\n" + "\n".join(f"{ts:%d/%m %H:%M:%S}: {'ngừng/chưa giám sát' if online is None else 'có phản hồi' if online else 'vắng ARP'}" for ts, online in rows))

    def export_csv(self):
        from extras.csv_export import export_devices
        path, _ = QFileDialog.getSaveFileName(self, "Xuất thiết bị", "netguard_devices.csv", "CSV (*.csv)")
        if path:
            try:
                export_devices(self.backend.list_devices(), path)
                self.statusBar().showMessage(f"Đã xuất CSV: {path}", 10000)
            except Exception as exc:
                QMessageBox.warning(self, "CSV", str(exc))

    def show_wifi(self):
        self.tabs.setCurrentWidget(self.report_tab)
        self.report_text.setPlainText("Đang quét Wi-Fi trong nền…")
        self.backend.run_wifi_scan()

    def show_settings(self):
        from core.settings import load, save, DEFAULTS
        try:
            values = load()
        except (OSError, ValueError, TypeError):
            values = dict(DEFAULTS)
        dialog = QDialog(self)
        dialog.setWindowTitle("Cài đặt - có hiệu lực sau khi mở lại")
        dialog.resize(640, 600)
        layout = QVBoxLayout(dialog)
        label = QLabel("Chọn card/dải quét và điều chỉnh ngưỡng theo mạng của bạn. Thay đổi có hiệu lực khi mở lại NetGuard. Tối đa 1.024 địa chỉ trong dải quét; kết quả ARP/ICMP chỉ phản ánh các quan sát.")
        label.setWordWrap(True)
        layout.addWidget(label)
        form = QFormLayout()
        editors = {}
        for key, title, low, high, integer in (
            ("scan_interval", "Chu kỳ quét (giây)", 5, 3600, False),
            ("ping_interval", "Chu kỳ ping (giây)", .2, 300, False),
            ("ping_timeout", "Chờ phản hồi ping (giây)", .1, 10, False),
            ("retention_days", "Giữ lịch sử (ngày)", 1, 3650, True),
            ("loss_bad_pct", "Ngưỡng mất gói (%)", 0, 100, False),
            ("router_rtt_ms", "Ngưỡng RTT router (ms)", 1, 1000, False),
            ("external_rtt_ms", "Ngưỡng RTT đích ngoài (ms)", 1, 5000, False)):
            editor = QSpinBox() if integer else QDoubleSpinBox()
            editor.setRange(low, high)
            editor.setValue(values[key])
            editors[key] = editor
            form.addRow(title, editor)
        for key, title, hint in (
            ("external_target", "Địa chỉ IPv4 đích ngoài", "Ví dụ 1.1.1.1"),
            ("scan_cidr", "Dải quét tùy chọn", "Để trống: toàn subnet; ví dụ 192.168.1.0/24"),
            ("interface_name", "Tên card ưu tiên", "Để trống: tự chọn; ví dụ Wi-Fi hoặc Ethernet"),
            ("network_label", "Nhãn hồ sơ mạng bổ sung", "Dùng nhãn riêng nếu Windows không nhận được hồ sơ mạng")):
            editor = QLineEdit(values[key])
            editor.setPlaceholderText(hint)
            editors[key] = editor
            form.addRow(title, editor)
        layout.addLayout(form)
        button = QPushButton("Lưu cấu hình")
        def store():
            try:
                result = {key: editor.text().strip() if isinstance(editor, QLineEdit) else editor.value() for key, editor in editors.items()}
                save(result)
                dialog.accept()
            except Exception as exc:
                QMessageBox.warning(dialog, "Cấu hình chưa hợp lệ", str(exc))
        button.clicked.connect(store)
        layout.addWidget(button)
        dialog.exec()

    def backup_database(self):
        path, _ = QFileDialog.getSaveFileName(self, "Sao lưu mạng hiện tại", "netguard_backup.sqlite", "SQLite (*.sqlite)")
        if path:
            try:
                self.backend.backup_database(path)
                self.statusBar().showMessage(f"Đã sao lưu: {path}", 10000)
            except Exception as exc:
                QMessageBox.critical(self, "Sao lưu", str(exc))

    def restore_database(self):
        path, _ = QFileDialog.getOpenFileName(self, "Khôi phục mạng hiện tại", "", "SQLite (*.sqlite *.db)")
        if path and QMessageBox.question(self, "Khôi phục", "Dừng theo dõi và khôi phục hồ sơ đang chọn từ bản sao này? Dữ liệu hiện tại sẽ được sao lưu trước.") == QMessageBox.Yes:
            try:
                self.backend.restore_database(path)
                self.refresh_devices()
                self.refresh_alerts()
            except Exception as exc:
                QMessageBox.critical(self, "Khôi phục", str(exc))

    def select_history(self):
        choices = self.backend.available_profiles()
        selected, ok = QInputDialog.getItem(self, "Hồ sơ mạng", "Chọn hồ sơ lịch sử (dừng theo dõi), hoặc quay lại theo dõi:", ["Theo dõi kết nối hiện tại"] + choices, 0, False)
        if ok:
            try:
                if selected == "Theo dõi kết nối hiện tại":
                    self.backend.start()
                else:
                    self.backend.select_history(selected)
                self.refresh_devices()
                self.refresh_alerts()
                self.refresh_diagnosis()
            except Exception as exc:
                QMessageBox.critical(self, "Hồ sơ mạng", str(exc))

    def closeEvent(self, event) -> None:
        if self.tray is not None and self.tray.isVisible() and self.tray.isSystemTrayAvailable() and not self.tray.icon().isNull():
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)



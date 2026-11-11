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

from PySide6.QtCore import QDateTime, Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDateTimeEdit,
    QDialog,
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
from ui.theme import ATTENTION_ROLE, BADGES, LightTable, apply_light_theme, badge_stylesheet

try:
    from pyqtgraph import PlotWidget
except Exception:  # pragma: no cover - fallback nếu môi trường thiếu pyqtgraph
    PlotWidget = QWidget

from backend import BackendBase
from models import Alert, Device, Diagnosis
from extras.mac_random import is_randomized


class DeviceDialog(QDialog):
    """Hộp thoại sửa tên và ghi chú thiết bị."""

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self.device = device
        self.setWindowTitle(f"Thiết bị {device.ip}")
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(device.name or "")
        self.note_edit = QLineEdit(device.note or "")
        form.addRow("Tên gợi nhớ:", self.name_edit)
        form.addRow("Ghi chú:", self.note_edit)
        layout.addLayout(form)

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


class MainWindow(QMainWindow):
    """Cửa sổ chính của NetGuard, tích hợp các màn hình monitor và báo cáo."""

    def __init__(self, backend: BackendBase, *, warnings: list[str] | None = None):
        super().__init__()
        self.backend = backend
        apply_light_theme(QApplication.instance())
        self._device_rows: dict[str, int] = {}
        self._refreshing = False
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
        self.refresh_action.setToolTip("Đọc lại kết nối đang dùng, quét thiết bị và lấy mẫu đo mới.")
        self.refresh_action.clicked.connect(self.request_network_refresh)
        self.toolbar.addWidget(self.refresh_action)

        self.trust_action = QPushButton("Tin cậy")
        self.trust_action.clicked.connect(self.toggle_selected_trust)
        self.toolbar.addWidget(self.trust_action)

        self.trust_all_action = QPushButton("Tin cậy tất cả")
        self.trust_all_action.clicked.connect(self.trust_all_devices)
        self.toolbar.addWidget(self.trust_all_action)

        self.rename_action = QPushButton("Sửa tên")
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

    def _connect_backend_signals(self) -> None:
        self.backend.device_updated.connect(self.on_device_updated)
        self.backend.alert_raised.connect(self.on_alert_raised)
        self.backend.diagnosis_changed.connect(self.on_diagnosis_changed)
        self.backend.ping_result.connect(self.on_ping_result)
        self.backend.connection_changed.connect(self.on_connection_changed)
        self.backend.measurement_changed.connect(self.on_measurement_changed)
        self.backend.devices_refreshed.connect(self.refresh_devices)
        self.backend.network_refresh_changed.connect(self.on_network_refresh_changed)

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
        if began:
            self._latest_diagnosis = None
            self._measurements = {}
            self.refresh_devices()
            self.refresh_diagnosis()

    def _init_devices_tab(self) -> None:
        layout = QVBoxLayout(self.devices_tab)
        layout.setContentsMargins(0, 12, 0, 0)
        self.device_table = LightTable()
        self.device_table.setObjectName("deviceTable")
        self.device_table.setColumnCount(10)
        self.device_table.setHorizontalHeaderLabels([
            "IP", "MAC", "HÃNG", "TÊN", "GHI CHÚ", "TRẠNG THÁI", "TIN CẬY",
            "CHƯA TIN CẬY", "MAC CỤC BỘ", "THẤY GẦN NHẤT",
        ])
        self.device_table.setAlternatingRowColors(True)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.device_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.device_table.cellChanged.connect(self._handle_device_cell_edit)
        self.device_table.itemChanged.connect(self._handle_device_item_changed)
        layout.addWidget(self.device_table)

    def _init_alerts_tab(self) -> None:
        layout = QVBoxLayout(self.alerts_tab)
        layout.setContentsMargins(0, 12, 0, 0)
        self.alert_banner = QLabel("Chưa có cảnh báo mới.")
        self.alert_banner.setWordWrap(True)
        self.alert_banner.setStyleSheet(badge_stylesheet("success"))
        layout.addWidget(self.alert_banner)
        self.alert_list = QListWidget()
        self.alert_list.setWordWrap(True)
        self.alert_list.setSpacing(4)
        layout.addWidget(self.alert_list)

    def _init_diagnosis_tab(self) -> None:
        layout = QVBoxLayout(self.diagnosis_tab)
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
        self.diagnosis_plot.setMinimumHeight(120)
        if PlotWidget is not QWidget:
            self.diagnosis_plot.setBackground("#FFFFFF")
            for axis in ("left", "bottom"):
                self.diagnosis_plot.getAxis(axis).setPen("#E3E8F0")
                self.diagnosis_plot.getAxis(axis).setTextPen("#64748B")
        layout.addWidget(self.diagnosis_plot)

    def _init_report_tab(self) -> None:
        layout = QVBoxLayout(self.report_tab)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(16)
        form = QFormLayout()
        self.start_time = QDateTimeEdit(QDateTime.currentDateTime())
        self.end_time = QDateTimeEdit(QDateTime.currentDateTime())
        self.start_time.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.end_time.setDisplayFormat("dd/MM/yyyy HH:mm")
        form.addRow("Từ:", self.start_time)
        form.addRow("Đến:", self.end_time)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.export_btn = QPushButton("Xuất báo cáo PDF")
        self.export_btn.setProperty("primary", True)
        self.export_btn.clicked.connect(self.export_report)
        buttons.addStretch()
        buttons.addWidget(self.export_btn)
        layout.addLayout(buttons)

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlaceholderText("Kết quả xuất báo cáo sẽ hiện ở đây.")
        layout.addWidget(self.report_text)

    def refresh_devices(self) -> None:
        self._refreshing = True
        devices = self.backend.list_devices()
        self.device_table.setRowCount(0)
        self._device_rows = {}
        statuses = [self.backend.get_device_status(device) for device in devices]
        for key, value in {
            "total": len(devices), "online": statuses.count("Online"),
            "pending": sum(status.startswith("Chưa xác minh") for status in statuses),
            "untrusted": sum(not device.trusted for device in devices),
        }.items():
            self._stat_values[key].setText(str(value))

        for device in devices:
            row_index = self.device_table.rowCount()
            self.device_table.insertRow(row_index)
            self._device_rows[device.mac] = row_index

            values = [
                device.ip,
                device.mac,
                device.vendor if device.vendor and device.vendor != "Unknown" else "Chưa xác định",
                device.name or "",
                device.note or "",
                self.backend.get_device_status(device),
                "" if device.trusted else "",
                "Không" if device.trusted else "Có",
                "Có" if is_randomized(device.mac) else "Không",
                device.last_seen.strftime("%d/%m %H:%M:%S"),
            ]

            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if col_index not in (3, 4, 6):
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col_index == 0 and (not device.trusted or is_randomized(device.mac)):
                    item.setData(ATTENTION_ROLE, "warning")
                if col_index == 6:
                    item = QTableWidgetItem()
                    item.setCheckState(Qt.Checked if device.trusted else Qt.Unchecked)
                    item.setFlags((item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
                if col_index == 8:
                    item.setToolTip("Bit quản lý cục bộ của MAC; không đủ để kết luận thiết bị lạ hoặc MAC ngẫu nhiên.")
                self.device_table.setItem(row_index, col_index, item)

        self.device_table.resizeColumnsToContents()
        self.device_table.setColumnWidth(1, max(176, self.device_table.columnWidth(1)))
        self.device_table.setColumnWidth(5, max(230, self.device_table.columnWidth(5)))
        self.device_table.horizontalHeader().setStretchLastSection(True)
        self._refreshing = False

    def refresh_alerts(self) -> None:
        alerts = self.backend.get_alerts(limit=20)
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
            tone = "danger" if alert.level == "danger" else "warning" if alert.level == "warning" else "success"
            background, foreground = BADGES[tone]
            item.setForeground(QColor(foreground))
            item.setBackground(QColor(background))
            self.alert_list.addItem(item)

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
        for row, (target, label) in enumerate((("router", "Router"), ("isp", "ISP"), ("external", "Internet"))):
            result = results.get(target)
            samples = history[target][-30:]
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
            return

        self.diagnosis_plot.clear()
        self.diagnosis_plot.showGrid(True, True, alpha=0.15)
        self.diagnosis_plot.setLabel("left", "RTT", units="ms", color="#64748B")
        self.diagnosis_plot.setLabel("bottom", "Thời gian so với hiện tại", units="s", color="#64748B")

        for target, label, color in [
            ("router", "Router", "#2563EB"),
            ("isp", "ISP", "#C2410C"),
            ("external", "Internet", "#15803D"),
        ]:
            samples = history.get(target, [])
            if not samples:
                continue
            stamp = now()
            x = [(sample.ts - stamp).total_seconds() for sample in samples]
            y = [sample.rtt_ms if sample.rtt_ms is not None else float("nan") for sample in samples]
            self.diagnosis_plot.plot(x, y, pen=color, name=label, connect="finite")

    @Slot(object)
    def on_connection_changed(self, status: dict) -> None:
        self._measurements = {}
        self._latest_diagnosis = None
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
        self._measurements = measurements
        self.refresh_diagnosis()

    @Slot(object)
    def on_device_updated(self, device: Device) -> None:
        self.refresh_devices()

    @Slot(object)
    def on_alert_raised(self, alert: Alert) -> None:
        self.refresh_alerts()
        if self.tray is not None:
            self.tray.notify("Cảnh báo NetGuard", alert.message, alert.level)

    @Slot(object)
    def on_diagnosis_changed(self, diagnosis: Diagnosis) -> None:
        self._latest_diagnosis = diagnosis
        self.refresh_diagnosis()

    @Slot(object)
    def on_ping_result(self, result) -> None:
        self.refresh_diagnosis()

    def _handle_device_item_changed(self, item):
        if self._refreshing or item is None:
            return
        if item.column() != 6:
            return
        for device in self.backend.list_devices():
            if self.device_table.item(self._device_rows.get(device.mac, -1), 0) is item:
                break
        checked = item.checkState() == Qt.Checked
        row_index = self.device_table.row(item)
        mac = None
        for device in self.backend.list_devices():
            if self._device_rows.get(device.mac) == row_index:
                mac = device.mac
                break
        if mac is not None:
            self.backend.set_trusted(mac, checked)

    def _handle_device_cell_edit(self, row, col):
        if self._refreshing:
            return
        if col not in (3, 4):
            return
        item = self.device_table.item(row, col)
        if item is None:
            return
        device = self._row_to_device(row)
        if device is None:
            return
        name = self.device_table.item(row, 3).text().strip() if self.device_table.item(row, 3) else ""
        note = self.device_table.item(row, 4).text().strip() if self.device_table.item(row, 4) else ""
        self.backend.rename(device.mac, name, note)

    def _row_to_device(self, row_index: int) -> Device | None:
        for device in self.backend.list_devices():
            if self._device_rows.get(device.mac) == row_index:
                return device
        return None

    def trust_all_devices(self) -> None:
        for device in self.backend.list_devices():
            if not device.trusted:
                self.backend.set_trusted(device.mac, True)
        self.refresh_devices()

    def toggle_selected_trust(self) -> None:
        selected_rows = sorted({index.row() for index in self.device_table.selectedIndexes()})
        if not selected_rows:
            return
        for row in selected_rows:
            device = self._row_to_device(row)
            if device is not None:
                self.backend.set_trusted(device.mac, not device.trusted)

    def rename_selected_device(self) -> None:
        row = self.device_table.currentRow()
        if row < 0:
            return
        device = self._row_to_device(row)
        if device is None:
            return
        dialog = DeviceDialog(device, self)
        if dialog.exec() == QDialog.Accepted:
            name, note = dialog.values()
            self.backend.rename(device.mac, name, note)

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
            self.backend.export_report(start, end, save_path)
            self.report_text.setPlainText(f"Xuất báo cáo thành công:\n{save_path}")
        except Exception as exc:  # pragma: no cover - UI-level handling
            QMessageBox.critical(self, "Lỗi xuất báo cáo", str(exc))

    def closeEvent(self, event) -> None:
        if self.tray is not None and self.tray.isVisible():
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)



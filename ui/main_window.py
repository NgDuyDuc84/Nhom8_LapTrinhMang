from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime, Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.tray import NetGuardTrayIcon

try:
    from pyqtgraph import PlotWidget
except Exception:  # pragma: no cover - fallback nếu môi trường thiếu pyqtgraph
    PlotWidget = QWidget

from backend import BackendBase
from models import Alert, Device, Diagnosis


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

    def __init__(self, backend: BackendBase):
        super().__init__()
        self.backend = backend
        self._device_rows: dict[str, int] = {}
        self._refreshing = False

        self.setWindowTitle("NetGuard - Giám sát mạng LAN")
        self.resize(1200, 760)

        self.toolbar = self.addToolBar("NetGuard")
        self.toolbar.setMovable(False)

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
        self.report_action.clicked.connect(self.export_report)
        self.toolbar.addWidget(self.report_action)

        self.tray = NetGuardTrayIcon(self)
        self.tray.show()
        self.tray.notify("NetGuard", "Ứng dụng đang chạy nền.", "info")

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

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
        self.refresh_devices()
        self.refresh_alerts()
        self.refresh_diagnosis()

    def _connect_backend_signals(self) -> None:
        self.backend.device_updated.connect(self.on_device_updated)
        self.backend.alert_raised.connect(self.on_alert_raised)
        self.backend.diagnosis_changed.connect(self.on_diagnosis_changed)
        self.backend.ping_result.connect(self.on_ping_result)

    def _init_devices_tab(self) -> None:
        layout = QVBoxLayout(self.devices_tab)
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(8)
        self.device_table.setHorizontalHeaderLabels([
            "IP",
            "MAC",
            "Hãng",
            "Tên",
            "Ghi chú",
            "Trạng thái",
            "Tin cậy",
            "Lạ",
        ])
        self.device_table.setAlternatingRowColors(True)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.device_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.device_table.cellChanged.connect(self._handle_device_cell_edit)
        self.device_table.itemChanged.connect(self._handle_device_item_changed)
        layout.addWidget(self.device_table)

    def _init_alerts_tab(self) -> None:
        layout = QVBoxLayout(self.alerts_tab)
        self.alert_banner = QLabel("Chưa có cảnh báo mới.")
        self.alert_banner.setStyleSheet(
            "QLabel { background: #e8f5e9; color: #1b5e20; padding: 10px; border-radius: 6px; }"
        )
        layout.addWidget(self.alert_banner)
        self.alert_list = QListWidget()
        layout.addWidget(self.alert_list)

    def _init_diagnosis_tab(self) -> None:
        layout = QVBoxLayout(self.diagnosis_tab)
        top = QHBoxLayout()
        self.verdict_label = QLabel("Đang chờ dữ liệu...")
        self.verdict_label.setStyleSheet("font-size: 18px; font-weight: 700; padding: 12px;")
        top.addWidget(self.verdict_label)
        layout.addLayout(top)

        self.diagnosis_text = QLabel("Chưa có kết quả chẩn đoán.")
        self.diagnosis_text.setWordWrap(True)
        self.diagnosis_text.setStyleSheet("font-size: 14px; padding: 6px;")
        layout.addWidget(self.diagnosis_text)

        self.diagnosis_plot = PlotWidget()
        self.diagnosis_plot.setMinimumHeight(260)
        layout.addWidget(self.diagnosis_plot)

    def _init_report_tab(self) -> None:
        layout = QVBoxLayout(self.report_tab)
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

        for device in devices:
            row_index = self.device_table.rowCount()
            self.device_table.insertRow(row_index)
            self._device_rows[device.mac] = row_index

            values = [
                device.ip,
                device.mac,
                device.vendor or "Unknown",
                device.name or "",
                device.note or "",
                "Online" if device.online else "Offline",
                "" if device.trusted else "",
                "Có" if device.randomized_mac else "Không",
            ]

            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_index == 5:
                    item.setForeground(QColor("#1b5e20" if device.online else "#b71c1c"))
                if col_index == 6:
                    item = QTableWidgetItem()
                    item.setCheckState(Qt.Checked if device.trusted else Qt.Unchecked)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if col_index == 7:
                    item = QTableWidgetItem("Có" if device.randomized_mac else "Không")
                    item.setForeground(QColor("#ff9800" if device.randomized_mac else "#4caf50"))
                self.device_table.setItem(row_index, col_index, item)

            # tô màu dòng nếu thiết bị lạ
            if not device.trusted:
                for col in range(self.device_table.columnCount()):
                    cell = self.device_table.item(row_index, col)
                    if cell is not None:
                        cell.setBackground(QColor("#fff3e0"))

        self.device_table.resizeColumnsToContents()
        self._refreshing = False

    def refresh_alerts(self) -> None:
        alerts = self.backend.get_alerts(limit=20)
        self.alert_list.clear()
        if not alerts:
            self.alert_banner.setText("Chưa có cảnh báo mới.")
            self.alert_banner.setStyleSheet(
                "QLabel { background: #e8f5e9; color: #1b5e20; padding: 10px; border-radius: 6px; }"
            )
            return

        self.alert_banner.setText(f"Có {len(alerts)} cảnh báo gần nhất.")
        self.alert_banner.setStyleSheet(
            "QLabel { background: #fff3e0; color: #e65100; padding: 10px; border-radius: 6px; }"
        )

        for alert in alerts:
            item = QListWidgetItem(f"[{alert.ts:%H:%M:%S}] {alert.level.upper()} - {alert.message}")
            if alert.level == "danger":
                item.setForeground(QColor("#b71c1c"))
            elif alert.level == "warning":
                item.setForeground(QColor("#f9a825"))
            else:
                item.setForeground(QColor("#2e7d32"))
            self.alert_list.addItem(item)

    def refresh_diagnosis(self) -> None:
        history = {
            "router": self.backend.get_ping_history("router", 30),
            "isp": self.backend.get_ping_history("isp", 30),
            "external": self.backend.get_ping_history("external", 30),
        }
        if not history["router"] and not history["isp"] and not history["external"]:
            self.verdict_label.setText("Đang chờ dữ liệu")
            self.verdict_label.setStyleSheet("font-size: 18px; font-weight: 700; padding: 12px; color: #757575;")
            self.diagnosis_text.setText("Chưa có mẫu ping nào để đánh giá.")
            return

        verdict = "ok"
        text = "Mạng bình thường."
        for name, samples in history.items():
            if samples and any(sample.rtt_ms is None for sample in samples):
                verdict = "warning"
        if self.backend is not None and hasattr(self.backend, "_diagnoses") and self.backend._diagnoses:
            latest = self.backend._diagnoses[-1]
            verdict = latest.verdict
            text = latest.text

        if verdict == "ok":
            color = "#1b5e20"
            css = "font-size: 18px; font-weight: 700; padding: 12px; color: #1b5e20;"
        elif verdict in {"home_issue", "isp_issue", "internet_issue"}:
            color = "#b71c1c"
            css = "font-size: 18px; font-weight: 700; padding: 12px; color: #b71c1c;"
        else:
            color = "#f9a825"
            css = "font-size: 18px; font-weight: 700; padding: 12px; color: #f9a825;"

        self.verdict_label.setText(verdict)
        self.verdict_label.setStyleSheet(css)
        self.diagnosis_text.setText(text)

        if PlotWidget is QWidget:
            self.diagnosis_plot.setVisible(False)
            return

        self.diagnosis_plot.clear()
        self.diagnosis_plot.showGrid(True, True, alpha=0.3)

        for target, label, color in [
            ("router", "Router", "#0d47a1"),
            ("isp", "ISP", "#ef6c00"),
            ("external", "Internet", "#2e7d32"),
        ]:
            samples = history.get(target, [])
            if not samples:
                continue
            x = list(range(len(samples)))
            y = [sample.rtt_ms if sample.rtt_ms is not None else None for sample in samples]
            valid_y = [(i, value) for i, value in enumerate(y) if value is not None]
            if valid_y:
                xs = [point[0] for point in valid_y]
                ys = [point[1] for point in valid_y]
                self.diagnosis_plot.plot(xs, ys, pen=color, name=label)

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
        save_path, _ = QFileDialog.getSaveFileName(self, "Lưu báo cáo PDF", default_path, "PDF Files (*.pdf)")
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


if __name__ == "__main__":
    app = QApplication([])
    from ui.fake_data import FakeBackend

    backend = FakeBackend()
    window = MainWindow(backend)
    backend.start()
    window.show()
    app.exec()

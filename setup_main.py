"""Giao diện bộ cài Full; chỉ cài sau khi người dùng bấm Cài đặt."""
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from installer.setup_core import bundled_payload, default_target, install, launch_app


class InstallWorker(QThread):
    progress = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.target = target

    def run(self):
        try:
            payload, expected = bundled_payload()
            self.completed.emit(install(payload, self.target, expected, self.progress.emit))
        except Exception as exc:
            self.failed.emit(str(exc))


class SetupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.result = None
        self.setWindowTitle("Cài đặt NetGuard Full")
        self.setMinimumWidth(620)
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        self.setWindowIcon(QIcon(str(root / "assets" / "netguard.svg")))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        title = QLabel("Cài đặt NetGuard Full")
        title.setStyleSheet("font-size:24px;font-weight:700;color:#1e293b")
        layout.addWidget(title)
        description = QLabel("Giám sát mạng LAN, quét thiết bị và nghe ARP bằng Npcap.\n\n"
                             "Nếu máy chưa có Npcap, bộ cài sẽ tải từ npcap.com và mở trình cài chính thức để bạn xác nhận. "
                             "Cần Internet cho lần tải này. Dữ liệu lịch sử hiện có được giữ lại.")
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addWidget(QLabel("Thư mục cài đặt:"))
        row = QHBoxLayout()
        self.folder = QLineEdit(str(default_target()))
        self.browse = QPushButton("Chọn thư mục…")
        self.browse.clicked.connect(self.choose_folder)
        row.addWidget(self.folder, 1)
        row.addWidget(self.browse)
        layout.addLayout(row)
        self.open_after = QCheckBox("Mở NetGuard Full sau khi cài xong")
        self.open_after.setChecked(True)
        layout.addWidget(self.open_after)
        license_label = QLabel('Npcap được sử dụng theo <a href="https://npcap.com/#download">giấy phép của Nmap</a>. '
                               'Bộ cài này không chứa sẵn bộ cài hay driver Npcap.')
        license_label.setOpenExternalLinks(True)
        license_label.setWordWrap(True)
        layout.addWidget(license_label)
        self.status = QLabel("Sẵn sàng cài đặt.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.close_btn = QPushButton("Đóng")
        self.close_btn.clicked.connect(self.close)
        self.install_btn = QPushButton("Cài đặt")
        self.install_btn.setDefault(True)
        self.install_btn.clicked.connect(self.start_install)
        buttons.addWidget(self.close_btn)
        buttons.addWidget(self.install_btn)
        layout.addLayout(buttons)
        self.setStyleSheet("QWidget{font-family:Segoe UI;font-size:14px;background:#f8fafc;color:#1e293b;}"
                           "QLineEdit{background:white;padding:8px;border:1px solid #cbd5e1;border-radius:5px;}"
                           "QPushButton{padding:9px 18px;background:#2563eb;color:white;border:0;border-radius:5px;}"
                           "QPushButton:disabled{background:#94a3b8;}")

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục cài NetGuard Full", self.folder.text())
        if folder:
            self.folder.setText(folder)

    def start_install(self):
        if not self.folder.text().strip():
            QMessageBox.warning(self, "Thiếu thư mục", "Hãy chọn thư mục cài đặt.")
            return
        for widget in (self.install_btn, self.close_btn, self.folder, self.browse, self.open_after):
            widget.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.worker = InstallWorker(Path(self.folder.text()), self)
        self.worker.progress.connect(self.status.setText)
        self.worker.failed.connect(self.failed)
        self.worker.completed.connect(self.completed)
        self.worker.finished.connect(self.set_idle)
        self.worker.start()

    def set_idle(self):
        self.progress_bar.setVisible(False)
        self.close_btn.setEnabled(True)
        if self.result is None:
            for widget in (self.install_btn, self.folder, self.browse, self.open_after):
                widget.setEnabled(True)
        elif self.open_after.isChecked() and not self.result.reboot_required:
            self.close_btn.setText("Đóng và mở NetGuard Full")

    def failed(self, message):
        self.status.setText(message)
        QMessageBox.warning(self, "Chưa hoàn tất cài đặt", message)

    def completed(self, result):
        self.result = result
        message = f"Đã cài NetGuard Full tại:\n{result.executable}"
        if result.reboot_required:
            message += "\n\nHãy khởi động lại Windows trước khi mở ứng dụng."
        if result.shortcut_error:
            message += "\n\nChưa tạo được lối tắt. Bạn có thể mở trực tiếp file EXE trong thư mục cài đặt."
        self.status.setText(message)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            event.ignore()
            return
        if self.result and self.open_after.isChecked() and not self.result.reboot_required:
            try:
                launch_app(self.result.executable)
            except OSError as exc:
                QMessageBox.warning(self, "Chưa mở được ứng dụng", str(exc))
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = SetupWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

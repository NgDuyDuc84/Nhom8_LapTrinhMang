from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from pathlib import Path


class NetGuardTrayIcon(QSystemTrayIcon):
    """Biểu tượng khay hệ thống cho NetGuard, giữ app chạy nền khi cửa sổ đóng."""

    def __init__(self, window=None, parent=None) -> None:
        super().__init__(parent)
        self.window = window
        self._build_menu()
        icon = QIcon.fromTheme("network-workgroup")
        if icon.isNull():
            icon = QIcon(str(Path(__file__).resolve().parent.parent / "assets" / "netguard.svg"))
        self.setIcon(icon)
        self.activated.connect(lambda reason: self._show_window() if reason == QSystemTrayIcon.DoubleClick else None)
        self.setToolTip("NetGuard")

    def _build_menu(self) -> None:
        menu = QMenu()
        self.show_action = QAction("Mở NetGuard", self)
        self.show_action.triggered.connect(self._show_window)
        menu.addAction(self.show_action)
        menu.addSeparator()
        self.quit_action = QAction("Thoát", self)
        self.quit_action.triggered.connect(self._quit_app)
        menu.addAction(self.quit_action)
        self.setContextMenu(menu)

    def _show_window(self) -> None:
        if self.window is None:
            return
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _quit_app(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def notify(self, title: str, message: str, level: str = "info") -> None:
        icon = QSystemTrayIcon.Information if level == "info" else QSystemTrayIcon.Warning if level == "warning" else QSystemTrayIcon.Critical
        self.showMessage(title, message, icon, 3000)
        self.setToolTip(f"NetGuard - {level.upper()}\n{message}")

    def show_status(self, message: str) -> None:
        self.setToolTip(f"NetGuard\n{message}")

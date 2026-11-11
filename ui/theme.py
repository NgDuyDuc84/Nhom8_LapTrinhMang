"""Bảng màu sáng và thành phần vẽ dùng chung cho NetGuard."""

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QTableWidget
from ui.device_columns import DeviceColumn as Col

BACKGROUND = "#F4F6FA"
TEXT = "#1E293B"
SECONDARY = "#64748B"
MUTED = "#94A3B8"
ACCENT = "#2563EB"
BORDER = "#E3E8F0"
BADGES = {
    "success": ("#DCFCE7", "#15803D"),
    "pending": ("#FEF3C7", "#B45309"),
    "warning": ("#FFEDD5", "#C2410C"),
    "danger": ("#FEE2E2", "#B91C1C"),
    "offline": ("#F1F5F9", "#64748B"),
}
ATTENTION_ROLE = int(Qt.UserRole) + 10

STYLESHEET = """
QWidget { color: #1E293B; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QDialog { background: #F4F6FA; }
QToolTip { background: #FFFFFF; color: #1E293B; border: 1px solid #E3E8F0; padding: 6px; }
QLabel { background: transparent; }
QLabel#brand { font-size: 19px; font-weight: 700; padding: 4px 16px 4px 8px; }
QLabel#pageTitle { font-size: 22px; font-weight: 700; }
QLabel#subtitle { color: #64748B; }
QLabel#connection { background: #FFFFFF; color: #475569; padding: 12px 16px;
    border: 1px solid #E3E8F0; border-radius: 10px; }
QLabel#environment { background: #FEF3C7; color: #B45309; padding: 10px 16px;
    border: 1px solid #FDE68A; border-radius: 8px; }
QFrame#statCard { background: #FFFFFF; border: 1px solid #E3E8F0; border-radius: 10px; }
QLabel#statValue { font-size: 24px; font-weight: 700; color: #1E293B; }
QLabel#statCaption { color: #64748B; font-size: 12px; }
QToolBar { background: #FFFFFF; border: none; border-bottom: 1px solid #E3E8F0;
    padding: 10px 16px; spacing: 8px; }
QPushButton { background: #FFFFFF; color: #1E293B; border: 1px solid #D5DCE6;
    border-radius: 7px; padding: 8px 13px; font-weight: 600; min-height: 18px; }
QPushButton:hover { background: #F0F5FF; border-color: #B8CCF4; }
QPushButton:pressed { background: #E0ECFF; }
QPushButton:focus { border-color: #2563EB; }
QPushButton:disabled { color: #94A3B8; background: #F1F5F9; border-color: #E3E8F0; }
QPushButton[primary="true"] { background: #2563EB; color: #FFFFFF; border-color: #2563EB; }
QPushButton[primary="true"]:hover { background: #1D4ED8; border-color: #1D4ED8; }
QPushButton[primary="true"]:pressed { background: #1E40AF; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: #64748B; border: none;
    border-bottom: 2px solid transparent; padding: 12px 20px; margin-right: 8px; font-weight: 600; }
QTabBar::tab:selected { color: #2563EB; border-bottom: 2px solid #2563EB; }
QTabBar::tab:hover:!selected { color: #1E293B; background: #F0F5FF; }
QTableWidget, QListWidget, QTextEdit { background: #FFFFFF; alternate-background-color: #FAFBFD;
    color: #1E293B; border: 1px solid #E3E8F0; border-radius: 10px;
    selection-background-color: #E0ECFF; selection-color: #1E293B; outline: none; }
QTableWidget { gridline-color: #EDF0F5; }
QHeaderView { background: #F1F4F9; }
QHeaderView::section { background: #F1F4F9; color: #64748B; font-size: 11px;
    font-weight: 600; padding: 12px 10px; border: none; border-bottom: 1px solid #E3E8F0; }
QTableCornerButton::section { background: #F1F4F9; border: none; }
QListWidget { padding: 8px; }
QListWidget::item { padding: 12px; margin: 3px; border: 1px solid #E3E8F0; border-radius: 8px; }
QListWidget::item:hover { background: #F0F5FF; }
QListWidget::item:selected { background: #E0ECFF; color: #1E293B; }
QLineEdit, QDateTimeEdit, QComboBox, QSpinBox { background: #FFFFFF; color: #1E293B;
    border: 1px solid #D5DCE6; border-radius: 7px; padding: 8px 10px;
    selection-background-color: #E0ECFF; selection-color: #1E293B; }
QLineEdit:focus, QDateTimeEdit:focus, QComboBox:focus { border-color: #2563EB; }
QTextEdit { padding: 12px; }
QMenu { background: #FFFFFF; color: #1E293B; border: 1px solid #E3E8F0; padding: 5px; }
QMenu::item { padding: 7px 18px; border-radius: 4px; }
QMenu::item:selected { background: #F0F5FF; color: #2563EB; }
QMenu::separator { height: 1px; background: #E3E8F0; margin: 5px; }
QScrollBar:vertical { background: #F4F6FA; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: #F4F6FA; height: 10px; margin: 2px; }
QScrollBar::handle { background: #CBD5E1; border-radius: 4px; min-height: 24px; min-width: 24px; }
QScrollBar::handle:hover { background: #94A3B8; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""


def apply_light_theme(app: QApplication) -> None:
    if app.property("netguardLightTheme"):
        return
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    palette = QPalette()
    for role, color in (
        (QPalette.Window, BACKGROUND), (QPalette.WindowText, TEXT),
        (QPalette.Base, "#FFFFFF"), (QPalette.AlternateBase, "#FAFBFD"),
        (QPalette.Text, TEXT), (QPalette.Button, "#FFFFFF"),
        (QPalette.ButtonText, TEXT), (QPalette.Highlight, "#E0ECFF"),
        (QPalette.HighlightedText, TEXT), (QPalette.PlaceholderText, MUTED),
        (QPalette.ToolTipBase, "#FFFFFF"), (QPalette.ToolTipText, TEXT),
        (QPalette.Link, ACCENT), (QPalette.Accent, ACCENT),
    ):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(MUTED))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(MUTED))
    app.setPalette(palette)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)
    app.setProperty("netguardLightTheme", True)


def badge_stylesheet(tone: str, *, large: bool = False) -> str:
    background, foreground = BADGES[tone]
    return (f"background: {background}; color: {foreground}; border-radius: 8px; "
            f"padding: 8px 12px; font-weight: 600; font-size: {16 if large else 13}px;")


class LightTable(QTableWidget):
    """Theo dõi hàng hover để cả hàng nhận cùng một màu nền."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hovered_row = -1
        self.setMouseTracking(True)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(46)
        self.horizontalHeader().setMinimumHeight(42)
        self.setAlternatingRowColors(True)
        self.setItemDelegate(LightTableDelegate(self))

    def mouseMoveEvent(self, event):
        row = self.rowAt(int(event.position().y()))
        if row != self.hovered_row:
            self.hovered_row = row
            self.viewport().update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hovered_row = -1
        self.viewport().update()
        super().leaveEvent(event)


class LightTableDelegate(QStyledItemDelegate):
    """Vẽ badge/checkbox theo cùng palette, giữ dữ liệu và thao tác của bảng."""

    def paint(self, painter: QPainter, option, index):
        table = self.parent()
        painter.save()
        selected = bool(option.state & QStyle.State_Selected)
        hover = index.row() == table.hovered_row
        background = "#E0ECFF" if selected else "#F0F5FF" if hover else (
            "#FAFBFD" if index.row() % 2 else "#FFFFFF"
        )
        painter.fillRect(option.rect, QColor(background))
        painter.setPen(QPen(QColor("#EDF0F5"), 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        rect = QRectF(option.rect).adjusted(12, 0, -10, -1)
        text = str(index.data(Qt.DisplayRole) or "")
        tone = None
        if table.objectName() == "deviceTable":
            if index.column() == Col.STATUS:
                tone = "success" if text == "Online" else "offline" if text == "Offline" else "pending"
            elif index.column() == Col.TYPE:
                tone = "pending" if "(gợi ý)" in text else "success" if "(đã chọn)" in text else None
            if index.column() == Col.TRUSTED:
                box = QRectF(0, 0, 17, 17)
                box.moveCenter(rect.center())
                checked = index.data(Qt.CheckStateRole) == Qt.Checked.value
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setPen(QPen(QColor(ACCENT if checked else "#CBD5E1"), 1.3))
                painter.setBrush(QColor(ACCENT if checked else "#FFFFFF"))
                painter.drawRoundedRect(box, 4, 4)
                if checked:
                    path = QPainterPath(QPointF(box.left() + 4, box.top() + 8.5))
                    path.lineTo(box.left() + 7, box.top() + 11.5)
                    path.lineTo(box.left() + 13, box.top() + 5)
                    painter.setPen(QPen(QColor("#FFFFFF"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    painter.drawPath(path)
                painter.restore()
                return
        if tone:
            fill, color = BADGES[tone]
            painter.setRenderHint(QPainter.Antialiasing)
            font = QFont(option.font)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            width = min(rect.width(), painter.fontMetrics().horizontalAdvance(text) + 18)
            badge = QRectF(rect.left(), rect.center().y() - 13, width, 26)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(fill))
            painter.drawRoundedRect(badge, 7, 7)
            painter.setPen(QColor(color))
            painter.drawText(badge.adjusted(9, 0, -9, 0), Qt.AlignVCenter | Qt.AlignLeft,
                             painter.fontMetrics().elidedText(text, Qt.ElideRight, max(0, int(width - 18))))
        else:
            color = MUTED if text in ("", "—", "Chưa xác định") else (
                SECONDARY if (table.objectName() == "deviceTable" and index.column() in (Col.MAC, Col.IP, Col.LAST_SEEN)) else TEXT
            )
            font = QFont(option.font)
            if table.objectName() == "deviceTable" and index.column() == Col.MAC:
                font.setFamily("Consolas")
                font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft,
                             painter.fontMetrics().elidedText(text or "—", Qt.ElideRight, max(0, int(rect.width()))))
        if index.column() == 0:
            attention = index.data(ATTENTION_ROLE)
            if attention:
                painter.fillRect(QRectF(option.rect.left(), option.rect.top(), 3, option.rect.height()),
                                 QColor(BADGES[attention][1]))
        painter.restore()

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        padding = 28 if index.column() == Col.STATUS else 24
        return QSize(hint.width() + padding, max(46, hint.height()))

    def editorEvent(self, event, model, option, index):
        if self.parent().objectName() == "deviceTable" and index.column() == Col.TRUSTED:
            if (event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton) or (
                event.type() == QEvent.KeyPress and event.key() == Qt.Key_Space
            ):
                checked = index.data(Qt.CheckStateRole) == Qt.Checked.value
                return model.setData(index, Qt.Unchecked if checked else Qt.Checked, Qt.CheckStateRole)
            return False
        return super().editorEvent(event, model, option, index)

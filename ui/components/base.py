from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedLayout,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components.icons import icon
from utils.styles import add_card_shadow, configure_table, make_badge, tone_for_status


class BasePage(QWidget):
    def __init__(self, title="", subtitle="", parent=None):
        super().__init__(parent)
        self.setObjectName("content_area")
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(20, 20, 20, 20)
        self.root_layout.setSpacing(14)
        if title:
            self.root_layout.addLayout(self._header(title, subtitle))

    def _header(self, title, subtitle):
        row = QHBoxLayout()
        block = QVBoxLayout()
        block.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("page_title")
        sub_label = QLabel(subtitle)
        sub_label.setObjectName("page_subtitle")
        block.addWidget(title_label)
        block.addWidget(sub_label)
        row.addLayout(block)
        row.addStretch()
        return row


class CardFrame(QFrame):
    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        add_card_shadow(self)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.outer.setSpacing(0)
        if title:
            header = QFrame()
            header.setObjectName("card_header")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(18, 13, 18, 13)
            label = QLabel(title)
            label.setObjectName("card_title")
            header_layout.addWidget(label)
            header_layout.addStretch()
            self.outer.addWidget(header)
        body = QFrame()
        body.setObjectName("card_body")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(18, 18, 18, 18)
        self.body_layout.setSpacing(12)
        self.outer.addWidget(body)


class StatusBadge(QLabel):
    def __init__(self, status, parent=None):
        super().__init__(str(status), parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(22)
        self.set_status(status)

    def set_status(self, status):
        self.setText(str(status))
        self.setObjectName(f"badge_{tone_for_status(status)}")
        self.style().unpolish(self)
        self.style().polish(self)


class DataTable(QWidget):
    def __init__(self, headers, empty_text="No records found", parent=None):
        super().__init__(parent)
        self._empty_text = empty_text
        self.stack = QStackedLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        configure_table(self.table)
        self.stack.addWidget(self.table)
        self.empty = self._make_empty()
        self.stack.addWidget(self.empty)
        self.set_empty(True)

    def _make_empty(self):
        frame = QFrame()
        frame.setObjectName("card_body")
        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignCenter)
        mark = QLabel()
        mark.setPixmap(icon("fa5s.inbox").pixmap(32, 32))
        mark.setAlignment(Qt.AlignCenter)
        label = QLabel(self._empty_text)
        label.setObjectName("stat_label")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(mark)
        layout.addWidget(label)
        return frame

    def set_empty(self, is_empty):
        self.stack.setCurrentWidget(self.empty if is_empty else self.table)


class LoadingOverlay(QFrame):
    def __init__(self, parent=None, text="Loading"):
        super().__init__(parent)
        self.setObjectName("alert_info")
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        label = QLabel(text)
        label.setObjectName("alert_text_info")
        layout.addWidget(label)

    def show_loading(self, text=None):
        if text:
            found = self.findChild(QLabel)
            if found:
                found.setText(text)
        self.setVisible(True)
        self.raise_()

    def hide_loading(self):
        self.setVisible(False)


def badge(status):
    return make_badge(status, tone_for_status(status))

from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from utils.styles import make_badge


class SettingsPage(QWidget):
    def __init__(self, current_role=None, display_name=None, permissions=None):
        super().__init__()
        self.current_role = current_role or "User"
        self.display_name = display_name or "User"
        self.permissions = set(permissions or ())
        self.setObjectName("content_area")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        header = QVBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("page_title")
        subtitle = QLabel("Account and system preferences")
        subtitle.setObjectName("page_subtitle")
        header.addWidget(title)
        header.addWidget(subtitle)
        root.addLayout(header)

        account = QFrame()
        account.setObjectName("card")
        account_layout = QVBoxLayout(account)
        account_layout.setContentsMargins(18, 16, 18, 16)
        account_layout.setSpacing(10)
        account_layout.addWidget(self._row("Signed in as", self.display_name))
        account_layout.addWidget(self._separator())
        account_layout.addWidget(self._row("Role", self.current_role))
        account_layout.addWidget(self._separator())
        account_layout.addWidget(self._row("Settings Access", "Visible to all users"))
        root.addWidget(account)

        permissions_card = QFrame()
        permissions_card.setObjectName("card")
        permissions_layout = QVBoxLayout(permissions_card)
        permissions_layout.setContentsMargins(18, 16, 18, 16)
        permissions_layout.setSpacing(10)
        count_label = QLabel("Enabled Task Count")
        count_label.setObjectName("form_label")
        permissions_layout.addWidget(count_label)
        permissions_layout.addWidget(make_badge(str(len(self.permissions)), "teal"))
        root.addWidget(permissions_card)
        root.addStretch()

    def _row(self, label, value):
        row = QFrame()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        left = QLabel(label)
        left.setObjectName("form_label")
        right = QLabel(value or "-")
        right.setObjectName("card_title")
        layout.addWidget(left)
        layout.addStretch()
        layout.addWidget(right)
        return row

    @staticmethod
    def _separator():
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setFixedHeight(1)
        return line

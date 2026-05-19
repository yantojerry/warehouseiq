from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui.components.icons import icon
from ui.styles import set_button_kind


class BaseDialog(QDialog):
    def __init__(
        self,
        parent=None,
        title="Message",
        message="",
        kind="info",
        confirm_text="OK",
        cancel_text=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setAttribute(Qt.WA_StyledBackground)
        self._result = False
        self._build_ui(title, message, kind, confirm_text, cancel_text)

    def _build_ui(self, title, message, kind, confirm_text, cancel_text):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        top = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(icon({
            "success": "fa5s.check-circle",
            "warning": "fa5s.exclamation-triangle",
            "error": "fa5s.times-circle",
            "info": "fa5s.info-circle",
        }.get(kind, "fa5s.info-circle")).pixmap(28, 28))
        top.addWidget(mark)
        title_label = QLabel(title)
        title_label.setObjectName("login_title")
        title_label.setWordWrap(True)
        top.addWidget(title_label, 1)
        layout.addLayout(top)

        body = QLabel(str(message))
        body.setObjectName("login_subtitle")
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QHBoxLayout()
        if cancel_text:
            cancel = QPushButton(cancel_text)
            set_button_kind(cancel, "outline")
            cancel.clicked.connect(self.reject)
            buttons.addWidget(cancel)
        buttons.addStretch()
        confirm = QPushButton(confirm_text)
        set_button_kind(confirm, "danger" if kind == "error" else "primary")
        confirm.clicked.connect(self.accept)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)

    def showEvent(self, event):
        super().showEvent(event)
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start(QPropertyAnimation.DeleteWhenStopped)


def info_dialog(parent, title, message):
    return BaseDialog(parent, title, message, "info").exec_()


def warning_dialog(parent, title, message):
    return BaseDialog(parent, title, message, "warning").exec_()


def error_dialog(parent, title, message):
    return BaseDialog(parent, title, message, "error").exec_()


def confirm_dialog(parent, title, message, confirm_text="Confirm", cancel_text="Cancel"):
    dialog = BaseDialog(parent, title, message, "warning", confirm_text, cancel_text)
    return dialog.exec_() == QDialog.Accepted

from PyQt5.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QTimer, Qt
from PyQt5.QtWidgets import QFrame, QLabel, QHBoxLayout


class Toast(QFrame):
    def __init__(self, parent, message, kind="info", duration=3000):
        super().__init__(parent)
        self.setObjectName(f"alert_{kind}")
        self.setWindowFlags(Qt.FramelessWindowHint)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        label = QLabel(message)
        label.setObjectName(f"alert_text_{kind}")
        layout.addWidget(label)
        self.adjustSize()
        self._duration = duration

    def show_toast(self):
        parent = self.parentWidget()
        if parent:
            margin = 20
            self.move(parent.width() - self.width() - margin, margin)
        self.setWindowOpacity(0.0)
        self.show()
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(180)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.start(QPropertyAnimation.DeleteWhenStopped)
        QTimer.singleShot(self._duration, self.close)


class ToastManager:
    def __init__(self, parent):
        self.parent = parent

    def show(self, message, kind="info"):
        toast = Toast(self.parent, message, kind)
        toast.show_toast()

    def success(self, message):
        self.show(message, "success")

    def warning(self, message):
        self.show(message, "warning")

    def error(self, message):
        self.show(message, "error")

    def info(self, message):
        self.show(message, "info")

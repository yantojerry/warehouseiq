import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui.login import LoginPage
from ui.main_window import MainWindow
from ui.components import error_dialog
from utils.api_client import ApiError, is_api_available, wait_for_api
from utils.styles import APP_THEME


def _start_backend_if_needed():
    if is_api_available():
        return None

    backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [sys.executable, backend_path],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    try:
        wait_for_api(timeout=20)
        return process
    except ApiError:
        process.terminate()
        raise


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("WarehouseIQ")

    font = QFont("Segoe UI", 11)
    app.setFont(font)

    app.setStyleSheet(APP_THEME)

    backend_process = None
    try:
        backend_process = _start_backend_if_needed()

        window_holder = {"window": None}

        def show_login():
            login_page = LoginPage()
            if login_page.exec_() == LoginPage.Accepted:
                window = MainWindow(
                    username=getattr(login_page, "authenticated_username", None),
                    display_name=getattr(login_page, "authenticated_display_name", None),
                    role=getattr(login_page, "authenticated_role", None),
                )
                window.logout_requested.connect(
                    lambda: (window.close(), show_login())
                )
                window_holder["window"] = window
                window.show()
                window.raise_()
                window.activateWindow()
            else:
                app.quit()

        show_login()

    except Exception as exc:
        error_dialog(None, "MIHS Startup Error", str(exc))
        return

    try:
        sys.exit(app.exec_())
    finally:
        if backend_process:
            backend_process.terminate()


if __name__ == "__main__":
    main()

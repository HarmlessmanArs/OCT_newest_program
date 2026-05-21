import sys
from PyQt6.QtWidgets import QApplication
from program.controllers.windows.main_window_controller import MainWindow


def gui_main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
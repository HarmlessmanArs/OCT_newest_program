import sys
from .libraries import *
from .ui.windows.main_window import MainWindow


def gui_main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
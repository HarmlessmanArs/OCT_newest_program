# Program.py
import sys
from PyQt6.QtWidgets import QApplication
from program.controllers.main_controller import MainController


def main():
    app = QApplication(sys.argv)

    # Инициализация Главного окна
    main_window = MainController()
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

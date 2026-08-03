# Program.py
import sys
from PyQt6.QtWidgets import QApplication
from program.controllers.main_controller import MainController

from program.state.user_settings_state import UserSettingsState
from program.state.temp_manager import TempWorkspace


def main():
    app = QApplication(sys.argv)

    settings = UserSettingsState.load()
    temp_workspace = TempWorkspace(custom_base_dir=settings.workspace_temp_folder)

    # Инициализация Главного окнац
    main_window = MainController(
        settings=settings,
        temp_workspace=temp_workspace
    )
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

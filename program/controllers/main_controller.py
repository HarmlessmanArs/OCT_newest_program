# program/controllers/main_controller.py
from PyQt6.QtWidgets import QMainWindow, QMdiSubWindow
from program.gui.windows.ui_main_window import Ui_MainWindow
from program.core.events import bus
from program.core.state import state


class MainController(QMainWindow):
    def __init__(self):
        super().__init__()
        # Подключаем ваш дизайн
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Настройка UI
        self._setup_connections()
        self._subscribe_to_events()

    def _setup_connections(self):
        """Привязка кнопок меню к шине событий"""
        # Пример: self.ui.actionNewProject.triggered.connect(self.on_new_project)
        pass

    def _subscribe_to_events(self):
        """Подписка на глобальные события"""
        bus.open_widget_requested.connect(self._handle_open_widget)
        bus.node_deleted.connect(self._handle_node_deleted)

    def _handle_open_widget(self, node_uid: str, widget_type: str):
        """Логика создания MDI окон"""
        if node_uid in state.active_mdi_windows:
            # Окно уже открыто, просто делаем его активным
            # window.setFocus() ...
            return

        # Здесь будет логика Factory для окон (Галерея, Графики)
        # new_widget = WidgetFactory.create(widget_type, node_uid)
        # sub_window = self.ui.mdiArea.addSubWindow(new_widget)
        # sub_window.show()
        # state.active_mdi_windows[node_uid] = sub_window
        pass

    def _handle_node_deleted(self, node_uid: str):
        """Абсолютно безопасное удаление окон (решение бага из прошлой версии)"""
        if node_uid in state.active_mdi_windows:
            sub = state.active_mdi_windows.pop(node_uid)
            sub.close()
            sub.deleteLater()
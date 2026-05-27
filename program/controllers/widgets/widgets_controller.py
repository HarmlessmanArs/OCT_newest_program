from PyQt6 import QtWidgets, QtGui, QtCore
from ...utils import LinkBase
from ...state.project_state.state import ProjectState


class WidgetsWindow(LinkBase, QtWidgets.QWidget):
    # Сигнал для уведомления MainWindow о закрытии окна
    window_closed = QtCore.pyqtSignal(object)

    def __init__(self, link_name, link_idx, obj_type, state: ProjectState | None, linked=None, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        LinkBase.__init__(self, link_name, link_idx, obj_type, linked)

        # НАСТРОЙКА: Флаг принудительного закрытия (без вызова QMessageBox)
        self.state = state
        self._force_close = False

        self._register_window_in_state()

    def _register_window_in_state(self):
        """
        Внутренний метод, который безопасно модифицирует центральное
        состояние проекта при рождении нового окна.
        """

        def mutation_logic(data: dict):
            # 1. Гарантируем наличие структуры дерева в данных
            if 'tree_structure' not in data:
                data['tree_structure'] = {}

            # 2. Формируем уникальный ключ для этого окна в проекте
            window_key = f"{self.obj_type}_{self.link_idx}"

            # 3. Записываем метаданные окна. Теперь проект ОКТ знает,
            # что у него существует и открыто такое окно обработки/просмотра.
            data['tree_structure'][window_key] = {
                "name": self.link_name,
                "type": self.obj_type,
                "index": str(self.link_idx),
                "is_active": True
            }

        # Вызываем метод обновления. Он изменит словарь И сам взведет флаг modified = True,
        # что мгновенно добавит звездочку '*' в заголовок главного окна.
        self.state.update_data(mutation_logic)

    def rename(self, new_name: str):
        self.link_name = new_name
        self.setWindowTitle(new_name)

    def closeEvent(self, event: QtGui.QCloseEvent):
        # Если удаление вызвано со стороны дерева — закрываем без лишних вопросов
        if self._force_close:
            event.accept()
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Confirmation",
            f"Close window {self.obj_type} named {self.link_name}?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No |
            QtWidgets.QMessageBox.StandardButton.Ignore
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.window_closed.emit(self)
            event.accept()
        elif reply == QtWidgets.QMessageBox.StandardButton.Ignore:
            event.ignore()
            if self.parent() and isinstance(self.parent(), QtWidgets.QMdiSubWindow):
                self.parent().showMinimized()
        else:
            event.ignore()
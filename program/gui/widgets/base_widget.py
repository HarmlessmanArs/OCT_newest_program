from PyQt6.QtWidgets import QWidget
from ...core.state import state
from ...core.events import bus

class BaseProjectWidget(QWidget):
    """Родительский класс для всех окон проекта"""
    def __init__(self, uid: str, parent=None):
        super().__init__(parent)
        self.uid = uid
        self.node = state.get_node(uid)

    def get_data(self):
        """Быстрый доступ к массивам данных (изображениям/таблицам) узла"""
        return self.node.data if self.node else None

    def update_data(self, new_data):
        """Сохраняет результаты обработки (OpenCV/NumPy) обратно в ядро"""
        if self.node:
            self.node.data = new_data
            state.set_modified(True)
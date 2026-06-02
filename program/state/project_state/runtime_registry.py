from PyQt6.QtWidgets import QWidget, QMdiSubWindow
from PyQt6.QtCore import QObject


class RuntimeRegistry(QObject):
    """
    Реестр живых UI-объектов программы (Этап 2).
    Связывает строковый UUID из State с реальными экземплярами окон и виджетов в RAM.
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        self.win = main_window

        # Хранилища живых ссылок
        self._widgets = {}  # {widget_uuid_str: QWidget}
        self._sub_windows = {}  # {widget_uuid_str: QMdiSubWindow}

    def register_widget(self, uuid_str: str, widget: QWidget, sub_window: QMdiSubWindow = None):
        """Регистрирует живые компоненты интерфейса."""
        uuid_str = str(uuid_str)  # <--- ФИКС 3: Нормализация ключа
        self._widgets[uuid_str] = widget
        if sub_window:
            self._sub_windows[uuid_str] = sub_window

    def get_widget(self, uuid_str: str) -> QWidget | None:
        return self._widgets.get(str(uuid_str))  # <--- ФИКС 4

    def get_sub_window(self, uuid_str: str) -> QMdiSubWindow | None:
        return self._sub_windows.get(str(uuid_str))  # <--- ФИКС 5

    def unregister_and_destroy(self, uuid_str: str):
        """
        Единый пайплайн удаления (Этап 9).
        """
        uuid_str = str(uuid_str)  # <--- ФИКС 6

        # 1. Безопасно извлекаем MDI контейнер
        sub = self._sub_windows.pop(uuid_str, None)

        if sub:
            widget_window = sub.widget()
            if widget_window and hasattr(widget_window, '_force_close'):
                widget_window._force_close = True

            try:
                sub.close()
                sub.deleteLater()
            except RuntimeError:
                pass

                # 2. Безопасно удаляем ссылку на сам виджет рабочих модулей
        self._widgets.pop(uuid_str, None)

    def clear_all(self):
        """Полная зачистка интерфейса перед загрузкой нового проекта (Этап 7)"""
        all_uuids = list(self._sub_windows.keys()) + list(self._widgets.keys())
        for uuid_str in set(all_uuids):
            self.unregister_and_destroy(uuid_str)

        self._widgets.clear()
        self._sub_windows.clear()
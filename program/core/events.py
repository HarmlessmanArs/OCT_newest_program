# program/core/events.py
from PyQt6.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    """
    Единая шина событий. Никакие окна не общаются напрямую.
    Всё идет через эти сигналы.
    """
    # Жизненный цикл проекта
    project_created = pyqtSignal()
    project_loaded = pyqtSignal(str)  # передаем путь
    project_saved = pyqtSignal()

    # Работа с деревом (Иерархия)
    node_added = pyqtSignal(str)  # передаем UUID узла
    node_deleted = pyqtSignal(str)  # передаем UUID удаленного узла
    node_selected = pyqtSignal(str)  # передаем UUID

    # Запросы от интерфейса к математике
    request_roi_processing = pyqtSignal(str)  # UUID картинки/галереи

    # Окна (MDI)
    open_widget_requested = pyqtSignal(str, str)  # UUID узла, тип виджета ('gallery', 'roi' и т.д.)


# Глобальный экземпляр шины
bus = EventBus()
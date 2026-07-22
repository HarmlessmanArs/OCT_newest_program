# program/core/events.py
from PyQt6.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    """
    Глобальная шина событий.
    Отвязывает логику от интерфейса: никто не вызывает методы чужих окон напрямую.
    """
    # --- Жизненный цикл проекта ---
    project_created = pyqtSignal()
    project_loaded = pyqtSignal(str)  # Передаем путь к файлу
    project_saved = pyqtSignal()
    project_modified = pyqtSignal(bool)  # Сигнал, чтобы зажечь [*] в заголовке окна

    # --- Изменения в данных (Дерево/Узлы) ---
    node_added = pyqtSignal(str)  # Передаем uid созданного узла
    node_removed = pyqtSignal(str)  # Передаем uid удаленного узла
    node_renamed = pyqtSignal(str, str)  # Передаем uid и новое имя

    # --- Интерфейс (MDI и Меню) ---
    request_open_widget = pyqtSignal(str)  # Запрос на открытие окна (передаем uid)
    active_widget_changed = pyqtSignal(str)  # Сменилось активное окно (передаем uid)

    # --- Вычислительные запросы (Для ваших imaging_*.ui модулей) ---
    request_processing = pyqtSignal(str, str)  # uid исходных данных, тип обработки (roi, boundaries)

    node_moved = pyqtSignal(str, str)


# Создаем глобальный экземпляр, который будем импортировать в другие файлы
bus = EventBus()
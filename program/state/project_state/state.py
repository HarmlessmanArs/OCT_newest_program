from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from ...project_storage.io.new import create_empty_project
from ...utils.paths import UserSettingsState


class ProjectState(QObject):
    """
    Единый источник правды (Single Source of Truth) для состояния проекта.
    Вся программа взаимодействует с данными и флагами ТОЛЬКО через этот класс.
    """
    # Сигналы, на которые будут подписываться любые окна программы
    sig_modified_changed = pyqtSignal(bool)  # Срабатывает при изменении статуса сохранен/нет
    sig_project_path_changed = pyqtSignal(Path)  # Срабатывает при смене имени/пути файла
    sig_data_reset = pyqtSignal()  # Срабатывает при сбросе (Новый проект)

    def __init__(self):
        super().__init__()

        # Загружаем настройки путей
        self.user_settings = UserSettingsState.load()

        # Внутренние переменные состояния
        self._current_path: Path | None = None
        self._modified: bool = False

        # Наш тяжелый/легкий каркас данных (snapshot проекта)
        self.project_data: dict = {}

        # Инициализируем пустой проект по умолчанию
        self.reset_to_new()

    @property
    def current_path(self) -> Path | None:
        return self._current_path

    @property
    def modified(self) -> bool:
        return self._modified

    def set_path(self, path: Path):
        """Меняет путь к проекту, обновляет конфиг пользователя и шлет сигнал в GUI"""
        self._current_path = path
        self.user_settings.last_save_project_folder = path.parent
        self.user_settings.save()
        self.sig_project_path_changed.emit(path)

    def set_modified(self, is_modified: bool):
        """Изменяет статус сохранности. Если статус изменился — уведомляет UI"""
        if self._modified != is_modified:
            self._modified = is_modified
            self.sig_modified_changed.emit(is_modified)

    def reset_to_new(self):
        """Сбрасывает состояние до чистого проекта"""
        self.project_data = create_empty_project(app_version="1.0")
        self._current_path = None
        self._modified = False

        # Оповещаем все окна, что проект стал абсолютно новым
        self.sig_data_reset.emit()
        self.sig_modified_changed.emit(False)

    def update_data(self, update_callback):
        """
        Универсальный метод для безопасного изменения данных проекта.
        Принимает функцию, которая мутирует self.project_data,
        и автоматически выставляет флаг модификации.
        """
        update_callback(self.project_data)
        self.set_modified(True)
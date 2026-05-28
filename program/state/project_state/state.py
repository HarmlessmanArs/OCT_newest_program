from pathlib import Path
import datetime
from PyQt6.QtCore import QObject, pyqtSignal

from .constants import WidgetTypes
from ...utils.paths import UserSettingsState


class ProjectState(QObject):
    """
    Единый источник правды (Single Source of Truth) для состояния проекта.
    Хранит ИСКЛЮЧИТЕЛЬНО сериализуемые данные. Никаких QWidget, QStandardItem или контроллеров!
    """
    # Сигналы для подписки UI-слоя
    sig_modified_changed = pyqtSignal(bool)  # Статус сохранения
    sig_project_path_changed = pyqtSignal(Path)  # Изменение пути к .bmip
    sig_data_reset = pyqtSignal()  # Полный сброс (Новый/Загруженный проект)

    # Сигналы тонкой настройки (чтобы не перерисовывать всё приложение целиком)
    sig_workspace_changed = pyqtSignal()  # Изменились позиции окон или активная вкладка

    def __init__(self):
        super().__init__()

        self.user_settings = UserSettingsState.load()

        self._current_path: Path | None = None
        self._modified: bool = False

        # Ссылка на открытый ProjectReader (Zarr ZipStore).
        # Хранится как runtime-свойство сессии, НЕ попадает в snapshot сохранения.
        self.reader_connection = None

        # Наш нормализованный каркас данных
        self.reset_to_new()

        self.project_data = {
            "project_meta": {},
            "hierarchy": [],  # Плоский список папок для быстрого поиска: [{"uuid":..., "text":..., "type": "folder"}]
            "widgets": {}  # Словарь дескрипторов виджетов: {uuid_str: descriptor_dict}
        }
        self._is_modified = False
        self.reader = None  # Ссылка на активный ProjectReader для ленивого чтения

    @property
    def current_path(self) -> Path | None:
        return self._current_path

    @property
    def modified(self) -> bool:
        return self._modified

    def set_path(self, path: Path):
        self._current_path = path
        self.user_settings.last_save_project_folder = path.parent
        self.user_settings.save()
        self.sig_project_path_changed.emit(path)

    def set_modified(self, is_modified: bool):
        if self._modified != is_modified:
            self._modified = is_modified
            self.sig_modified_changed.emit(is_modified)

    def reset_to_new(self):
        """Инициализирует структуру абсолютно чистого проекта (Этап 8)"""
        # Безопасно закрываем старый ридер, если он держал файл .bmip
        if self.reader_connection:
            try:
                self.reader_connection.close()
            except:
                pass
            self.reader_connection = None

        self.project_data = {
            "project_meta": {
                "app_version": "2.0",
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": "New project"
            },
            "hierarchy": [
                {
                    "uuid": "root_folder_0",
                    "type": WidgetTypes.FOLDER,
                    "text": "Folder 0",
                    "children": []
                }
            ],
            "datablocks": {},  # Ключи - UUID датаблоков. Внутри - снимки из .bmip (images, tables...)
            "widgets": {},  # Ключи - UUID виджетов. Внутри - Widget Descriptors (Этап 4)
            "workspace": {  # Геометрия и персистентность MDI (Этап 10)
                "active_widget_uuid": None,
                "mdi_positions": {}  # {widget_uuid: {"geometry": [...], "is_maximized": bool}}
            }
        }
        self._current_path = None
        self._modified = False

        self.sig_data_reset.emit()
        self.sig_modified_changed.emit(False)

    def load_from_snapshot(self, snapshot: dict, path: Path, reader):
        """Загружает десериализованные данные из воркера загрузки (Этап 7)"""
        self.project_data = snapshot
        self._current_path = path
        self.reader_connection = reader
        self._modified = False

        self.sig_data_reset.emit()
        self.sig_modified_changed.emit(False)

    # =========================================================================
    # API ДЛЯ УПРАВЛЕНИЯ ВУДЖЕТ-ДЕСКРИПТОРАМИ (ЭТАП 4)
    # =========================================================================

    def add_widget_descriptor(self, widget_uuid: str, widget_type: str, title: str, parent_block_uuid: str = None,
                              settings: dict = None):
        """Регистрирует дескриптор нового окна в состоянии проекта"""
        if widget_uuid in self.project_data["widgets"]:
            return

        self.project_data["widgets"][widget_uuid] = {
            "uuid": widget_uuid,
            "type": widget_type,
            "title": title,
            "parent_block_uuid": parent_block_uuid,
            "settings": settings or {}
        }
        self.set_modified(True)

    def remove_widget_descriptor(self, widget_uuid: str):
        """Удаляет дескриптор окна из состояния"""
        if widget_uuid in self.project_data["widgets"]:
            del self.project_data["widgets"][widget_uuid]

            # Чистим геометрию этого окна из воркспейса
            if widget_uuid in self.project_data["workspace"]["mdi_positions"]:
                del self.project_data["workspace"]["mdi_positions"][widget_uuid]

            self.set_modified(True)

    def update_widget_settings(self, widget_uuid: str, settings_update: dict):
        """Обновляет внутренние настройки конкретного окна (например, zoom или выбранный скан)"""
        if widget_uuid in self.project_data["widgets"]:
            self.project_data["widgets"][widget_uuid]["settings"].update(settings_update)
            self.set_modified(True)

    # =========================================================================
    # API ДЛЯ СИНХРОНИЗАЦИИ WORKSPACE PERSISTENCE (ЭТАП 10)
    # =========================================================================

    def update_workspace_state(self, active_uuid: str | None, positions: dict):
        """Обновляет глобальное состояние MDI-зоны (какие окна где открыты)"""
        self.project_data["workspace"]["active_widget_uuid"] = active_uuid
        self.project_data["workspace"]["mdi_positions"].update(positions)
        # Изменение геометрии окон обычно не ставит маркер "*" (modified = True) проекта,
        # но мы шлем сигнал, чтобы заинтересованные службы отреагировали
        self.sig_workspace_changed.emit()

    def hydrate_from_snapshot(self, snapshot: dict, reader_instance):
        """Заполняет State данными из считанного файла (Этап 8)."""
        self.reader = reader_instance
        self.project_data["project_meta"] = snapshot.get("project_meta", {})
        self.project_data["widgets"] = snapshot.get("blocks", {})

        # Восстанавливаем плоский список папок из сохраненного дерева структур
        self.project_data["hierarchy"] = []
        self._extract_folders_from_tree(snapshot.get("tree_structure", {}))

    def _extract_folders_from_tree(self, node: dict):
        """Вспомогательный метод для заполнения плоского списка папок."""
        if node.get("type") == "folder":
            self.project_data["hierarchy"].append({
                "uuid": node["uuid"],
                "type": "folder",
                "text": node["text"]
            })
        for child in node.get("children", []):
            self._extract_folders_from_tree(child)

    def get_complete_snapshot(self) -> dict:
        """Собирает полный снапшот для передачи в SaveProjectWorker."""
        return {
            "project_meta": self.project_data.get("project_meta", {}),
            "tree_structure": self.build_tree_structure_snapshot(),
            "blocks": self.project_data.get("widgets", {})
        }

    def build_tree_structure_snapshot(self) -> dict:
        """
        [ВАЖНО] Собирает текущую иерархию из QTreeView обратно в JSON-дерево.
        Этот метод вызывается прямо перед сохранением.
        """
        # Сюда передается ссылка на вашу модель tree_model из главного окна
        # Реализуется через обход строк модели от invisibleRootItem
        # (Ниже покажем логику генерации)
        pass
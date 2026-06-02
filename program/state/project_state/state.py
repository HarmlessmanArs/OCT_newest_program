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
    sig_project_loaded = pyqtSignal()

    # Сигналы тонкой настройки (чтобы не перерисовывать всё приложение целиком)
    sig_workspace_changed = pyqtSignal()  # Изменились позиции окон или активная вкладка

    def __init__(self):
        super().__init__()

        self.user_settings = UserSettingsState.load()

        self._current_path: Path | None = None
        self._modified: bool = False

        # Ссылка на открытый ProjectReader (Zarr ZipStore).
        # Хранится как runtime-свойство сессии, НЕ попадает в snapshot сохранения.
        self.project_reader = None
        self._is_modified = False
        self.reader = None  # Ссылка на активный ProjectReader для ленивого чтения
        # Наш нормализованный каркас данных
        self.project_data = {
            "project_meta": {},
            "hierarchy": [],  # Плоский список папок для быстрого поиска: [{"uuid":..., "text":..., "type": "folder"}]
            "widgets": {}  # Словарь дескрипторов виджетов: {uuid_str: descriptor_dict}
        }

        self.reset_to_new()


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
        if self.project_reader:
            try:
                self.project_reader.close()
            except:
                pass
            self.project_reader = None

        self.project_data = {
            "project_meta": {
                "app_version": "2.0",
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": "New project"
            },
            "hierarchy": [],  # ТЕПЕРЬ ТУТ ЧИСТО: папка создастся через контроллер динамически
            "datablocks": {},
            "widgets": {},
            "workspace": {
                "active_widget_uuid": None,
                "mdi_positions": {}
            }
        }
        self._current_path = None
        self._modified = False

        self.sig_data_reset.emit()
        self.sig_modified_changed.emit(False)

    def load_from_snapshot(self, snapshot: dict, path: Path, reader):
        """Загружает десериализованные данные из воркера загрузки (Этап 7)"""
        self._current_path = path
        self.reader = reader
        self.project_reader = reader  # Привязываем ридер к сессии для ленивого чтения

        # Нормализуем структуру: раскладываем транспортные ключи по внутренним полочкам State
        self.project_data = {
            "project_meta": snapshot.get("project_meta", {}),
            "hierarchy": snapshot.get("hierarchy", []),
            "widgets": snapshot.get("widgets", {}),
            "workspace": snapshot.get("workspace") or {"active_widget_uuid": None, "mdi_positions": {}},
            "datablocks": snapshot.get("blocks", {})  # Исправляем маппинг: blocks -> datablocks!
        }

        # Защита: если открыли старый файл (где плоские структуры пустые), распаковываем дерево
        if not self.project_data["hierarchy"] and not self.project_data["widgets"]:
            self.project_data["hierarchy"] = []
            self.project_data["widgets"] = {}
            self._extract_folders_from_tree(snapshot.get("tree_structure", {}))

        self._modified = False

        # Оповещаем UI-слой, что данные полностью обновились
        self.sig_project_path_changed.emit(path)
        self.sig_data_reset.emit()
        self.sig_modified_changed.emit(False)

    # =========================================================================
    # API ДЛЯ УПРАВЛЕНИЯ ВУДЖЕТ-ДЕСКРИПТОРАМИ (ЭТАП 4)
    # =========================================================================

        # =========================================================================
        # API ДЛЯ УПРАВЛЕНИЯ ПАПКАМИ (ИЕРАРХИЕЙ)
        # =========================================================================

    def add_folder_descriptor(self, folder_uuid: str, text: str, parent_uuid: str = None):
        """Регистрирует новую папку в плоском состоянии проекта."""
        if any(f["uuid"] == folder_uuid for f in self.project_data["hierarchy"]):
            return

        self.project_data["hierarchy"].append({
            "uuid": folder_uuid,
            "type": "folder",
            "text": text,
            "parent_uuid": parent_uuid
        })
        self.set_modified(True)

    def remove_folder_descriptor(self, folder_uuid: str):
        """Удаляет папку из состояния проекта."""
        self.project_data["hierarchy"] = [
            f for f in self.project_data["hierarchy"] if f["uuid"] != folder_uuid
        ]
        self.set_modified(True)

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
        """Заполняет State данными из считанного файла (Обеспечивает обратную совместимость)."""
        self.reader = reader_instance
        self.project_reader = reader_instance  # Подстраховка для обоих полей runtime-сессии

        # Восстанавливаем базовые метаданные проекта и воркспейс
        self.project_data["project_meta"] = snapshot.get("project_meta", {})
        self.project_data["workspace"] = snapshot.get("workspace") or {
            "active_widget_uuid": None,
            "mdi_positions": {}
        }

        # СЦЕНАРИЙ А: Файл нового образца (уже содержит плоские структуры данных)
        if "hierarchy" in snapshot or "widgets" in snapshot:
            self.project_data["hierarchy"] = snapshot.get("hierarchy") or []
            self.project_data["widgets"] = snapshot.get("widgets") or {}

        # СЦЕНАРИЙ Б: Старый файл (совместимость снизу вверх — распаковываем дерево)
        else:
            self.project_data["hierarchy"] = []
            self.project_data["widgets"] = {}
            self._extract_folders_from_tree(snapshot.get("tree_structure", {}))

        # Обнуляем оперативную память для тяжелых блоков (они будут лениво читаться через reader по UUID)
        self.project_data["datablocks"] = {}

    def _extract_folders_from_tree(self, node: dict):
        """Вспомогательный метод для распаковки старого дерева в плоские структуры (hierarchy и widgets)."""
        if not node or not isinstance(node, dict):
            return

        node_type = node.get("type")

        # 1. Если это папка — отправляем в плоский список hierarchy
        if node_type == "folder":
            self.project_data["hierarchy"].append({
                "uuid": node.get("uuid"),
                "type": "folder",
                "text": node.get("text", "Folder")
            })

        # 2. Если это виджет/окно из старого файла — конвертируем в плоский словарь widgets
        elif node_type == "widget" or (node_type and "widget" in str(node_type)):
            w_uuid = node.get("uuid")
            if w_uuid:
                self.project_data["widgets"][w_uuid] = {
                    "uuid": w_uuid,
                    "type": node.get("widget_type") or node_type,
                    "title": node.get("text") or node.get("title", "Window"),
                    "parent_block_uuid": node.get("parent_block_uuid"),
                    "settings": node.get("settings") or {}
                }

        # 3. Рекурсивно спускаемся по дереву детей
        children_list = node.get("children") or []
        for child in children_list:
            self._extract_folders_from_tree(child)

    def get_complete_snapshot(self) -> dict:
        """Собирает полный снапшот для передачи в SaveProjectWorker."""
        # Теперь мы передаем данные в строгом соответствии с ожиданиями ProjectWriter:
        # Легковесные метаданные структуры уходят в корень, а тяжелые массивы — в blocks.
        return {
            "project_meta": self.project_data.get("project_meta", {}),
            "hierarchy": self.project_data.get("hierarchy", []),
            "widgets": self.project_data.get("widgets", {}),
            "workspace": self.project_data.get("workspace", {}),
            "blocks": self.project_data.get("datablocks", {})  # Реальные тяжелые данные (сканы, массивы)
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
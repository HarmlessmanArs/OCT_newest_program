from pathlib import Path
import datetime
import re
from PyQt6.QtCore import QObject, pyqtSignal

from .constants import WidgetTypes
from ...utils.paths import UserSettingsState


class ProjectState(QObject):
    """
    Единый источник правды (Single Source of Truth) для состояния проекта.
    Хранит ИСКЛЮЧИТЕЛЬНО сериализуемые данные и структуру датаблоков (SAVE.md).
    """
    # Сигналы для подписки UI-слоя
    sig_modified_changed = pyqtSignal(bool)
    sig_project_path_changed = pyqtSignal(Path)
    sig_data_reset = pyqtSignal()
    sig_project_loaded = pyqtSignal()
    sig_workspace_changed = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.user_settings = UserSettingsState.load()

        self._current_path: Path | None = None
        self._modified: bool = False

        # Ссылка на открытый ProjectReader (Zarr ZipStore) для ленивого чтения
        self.project_reader = None

        # Наш нормализованный каркас данных
        self.project_data = {
            "project_meta": {},
            "hierarchy": [],
            "widgets": {},
            "workspace": {
                "active_widget_uuid": None,
                "mdi_positions": {}
            },
            "datablocks": {}  # <-- Здесь будет жить структура из SAVE.md
        }

        self.reset_to_new()

    @staticmethod
    def _clean_uuid(val) -> str:
        """
        Извлекает чистую строку UUID в формате {xxxx-xxxx...} из любых объектов.
        Гарантирует 100% совпадение ключей при сохранении и загрузке.
        """
        if not val:
            return ""

        if hasattr(val, 'toString'):
            return val.toString()

        val_str = str(val)
        match = re.search(r'\{[0-9a-fA-F\-]{36}\}', val_str)
        if match:
            return match.group(0)

        return val_str

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
        """Инициализирует структуру абсолютно чистого проекта"""
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
                "name": "New project",
                "description": ""
            },
            "hierarchy": [],
            "widgets": {},
            "workspace": {
                "active_widget_uuid": None,
                "mdi_positions": {}
            },
            "datablocks": {}
        }
        self._current_path = None
        self._modified = False

        self.sig_data_reset.emit()
        self.sig_modified_changed.emit(self._modified)

    # =========================================================================
    # УПРАВЛЕНИЕ ДАННЫМИ (DATABLOCKS согласно SAVE.md)
    # =========================================================================

    def add_datablock(self, block_uuid: str, metadata: dict = None):
        """
        Создает новый пустой датаблок по стандарту SAVE.md.
        """
        block_uuid = self._clean_uuid(block_uuid)

        if block_uuid in self.project_data["datablocks"]:
            return

        self.project_data["datablocks"][block_uuid] = {
            "metadata": metadata or {},
            "data_information": {},
            "original_images": {},
            "boundaries_images": {},
            "mu_t_images": {},
            "tables": {},
            "graphs": {},
            "hidden_data": {
                "boundaries_list": [],
                "mu_t_list": [],
                "av_int_list": []
            },
            "parameter_calculation": {
                "non_array_parameters": {},
                "array_parameters": {}
            }
        }
        self.set_modified(True)

    def get_datablock(self, block_uuid: str) -> dict:
        """Возвращает датаблок по его UUID или пустой словарь."""
        block_uuid = self._clean_uuid(block_uuid)
        return self.project_data["datablocks"].get(block_uuid, {})

    # =========================================================================
    # БЕЗОПАСНЫЕ CRUD-ОПЕРАЦИИ С ИНТЕРФЕЙСОМ (Со строгой типизацией UUID)
    # =========================================================================

    def add_folder_descriptor(self, folder_uuid: str, text: str, parent_uuid: str = None):
        folder_uuid = self._clean_uuid(folder_uuid)
        parent_uuid = self._clean_uuid(parent_uuid) if parent_uuid else None

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
        folder_uuid = self._clean_uuid(folder_uuid)
        self.project_data["hierarchy"] = [
            f for f in self.project_data["hierarchy"] if f["uuid"] != folder_uuid
        ]
        self.set_modified(True)

    def add_widget_descriptor(self, widget_uuid: str, widget_type: str, title: str, parent_block_uuid: str = None,
                              settings: dict = None):
        widget_uuid = self._clean_uuid(widget_uuid)
        parent_block_uuid = self._clean_uuid(parent_block_uuid) if parent_block_uuid else None

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
        widget_uuid = self._clean_uuid(widget_uuid)
        if widget_uuid in self.project_data["widgets"]:
            del self.project_data["widgets"][widget_uuid]

            if widget_uuid in self.project_data["workspace"]["mdi_positions"]:
                del self.project_data["workspace"]["mdi_positions"][widget_uuid]

            self.set_modified(True)

    def update_widget_settings(self, widget_uuid: str, settings_update: dict):
        widget_uuid = self._clean_uuid(widget_uuid)
        if widget_uuid in self.project_data["widgets"]:
            self.project_data["widgets"][widget_uuid]["settings"].update(settings_update)
            self.set_modified(True)

    # =========================================================================
    # СИНХРОНИЗАЦИЯ WORKSPACE И I/O (PERSISTENCE)
    # =========================================================================

    def update_workspace_state(self, active_uuid: str | None, positions: dict):
        active_uuid = self._clean_uuid(active_uuid) if active_uuid else None
        self.project_data["workspace"]["active_widget_uuid"] = active_uuid

        # Очищаем ключи позиций на всякий случай
        clean_positions = {self._clean_uuid(k): v for k, v in positions.items()}
        self.project_data["workspace"]["mdi_positions"].update(clean_positions)

        self.sig_workspace_changed.emit()

    def hydrate_from_snapshot(self, snapshot: dict, reader_instance):
        """Заполняет State данными из считанного файла (БЕЗ ЭМИТА СИГНАЛОВ)."""
        self.project_reader = reader_instance

        self.project_data["project_meta"] = snapshot.get("project_meta", {})
        self.project_data["workspace"] = snapshot.get("workspace") or {
            "active_widget_uuid": None,
            "mdi_positions": {}
        }

        if "hierarchy" in snapshot or "widgets" in snapshot:
            self.project_data["hierarchy"] = snapshot.get("hierarchy") or []
            self.project_data["widgets"] = snapshot.get("widgets") or {}
        else:
            self.project_data["hierarchy"] = []
            self.project_data["widgets"] = {}
            self._extract_folders_from_tree(snapshot.get("tree_structure", {}))

        # Важно: При гидратации мы можем загрузить только скелет датаблоков,
        # а тяжелые данные (массивы) ProjectReader будет вытаскивать лениво по запросу
        self.project_data["datablocks"] = snapshot.get("blocks", {})

    def _extract_folders_from_tree(self, node: dict):
        if not node or not isinstance(node, dict):
            return

        node_type = node.get("type")

        if node_type == "folder":
            self.project_data["hierarchy"].append({
                "uuid": self._clean_uuid(node.get("uuid")),
                "type": "folder",
                "text": node.get("text", "Folder"),
                "parent_uuid": None  # Совместимость со старым форматом
            })

        elif node_type == "widget" or (node_type and "widget" in str(node_type)):
            w_uuid = self._clean_uuid(node.get("uuid"))
            if w_uuid:
                self.project_data["widgets"][w_uuid] = {
                    "uuid": w_uuid,
                    "type": node.get("widget_type") or node_type,
                    "title": node.get("text") or node.get("title", "Window"),
                    "parent_block_uuid": self._clean_uuid(node.get("parent_block_uuid")),
                    "settings": node.get("settings") or {}
                }

        children_list = node.get("children") or []
        for child in children_list:
            self._extract_folders_from_tree(child)

    def get_complete_snapshot(self) -> dict:
        return {
            "project_meta": self.project_data.get("project_meta", {}),
            "hierarchy": self.project_data.get("hierarchy", []),
            "widgets": self.project_data.get("widgets", {}),
            "workspace": self.project_data.get("workspace", {}),
            "blocks": self.project_data.get("datablocks", {})
        }
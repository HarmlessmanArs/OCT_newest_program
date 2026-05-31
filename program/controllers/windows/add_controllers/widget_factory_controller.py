from PyQt6 import QtCore
from PyQt6.QtWidgets import QMdiSubWindow
from PyQt6.QtGui import QStandardItem
from PyQt6.QtCore import Qt, QObject, QUuid

from ....state.project_state.constants import WidgetTypes


class WidgetFactoryController(QObject):
    """
    Отвечает за генерацию новых окон и восстановление старых окон из дескрипторов.
    Интегрирован с RuntimeRegistry и ProjectState.
    """

    def __init__(self, main_window, project_state):
        super().__init__(main_window)
        self.win = main_window
        self.state = project_state

        # Ленивая инициализация рантайм-реестра в главном окне
        if not hasattr(self.win, 'runtime_registry'):
            from ....state.project_state.runtime_registry import RuntimeRegistry
            self.win.runtime_registry = RuntimeRegistry(self.win)

        self.registry = self.win.runtime_registry

        # ФИКС 1: Явно собираем и сохраняем реестр классов при инициализации фабрики
        self._window_registry: dict = self._build_window_registry()

    @staticmethod
    def _build_window_registry() -> dict:
        """Внутренний хелпер для ленивого импорта классов окон во избежание круговых зависимостей."""
        from ...widgets.gallery_controller import GalleryWindow
        from ...widgets.table_controller import TableWindow
        from ...widgets.graph_controller import GraphWindow
        from ...widgets.imaging_boundaries_controller import ImagingBoundariesWindow
        from ...widgets.imaging_mu_t_controller import ImagingMuTWindow
        from ...widgets.imaging_av_int_controller import ImagingAvIntWindow
        from ...widgets.imaging_roi_controller import ImagingROIWindow

        # ФИКС 2: Исправлена опечатка в маппинге "graph" -> GraphWindow
        return {
            "gallery": GalleryWindow,
            "table": TableWindow,
            "graph": GraphWindow,
            "imaging_boundaries": ImagingBoundariesWindow,
            "imaging_mu_t": ImagingMuTWindow,
            "imaging_av_int": ImagingAvIntWindow,
            "imaging_roi": ImagingROIWindow,
        }

    # =========================================================================
    # СОЗДАНИЕ НОВЫХ ОБЪЕКТОВ ИЗ GUI (Вызывается пользователем)
    # =========================================================================

    def create_folder(self, name: str = None) -> QStandardItem:
        """Создает новую папку в состоянии и отображает её в дереве."""
        if not name:
            name = f'Folder_{self.win.folder_count}'
            self.win.folder_count += 1

        folder_uuid = QUuid.createUuid().toString()

        # --- КРИТИЧЕСКИЙ ФИКС: Синхронизируем добавление папки со State ---
        if "hierarchy" not in self.state.project_data:
            self.state.project_data["hierarchy"] = []

        # self.state.project_data["hierarchy"].append({
        #     "uuid": folder_uuid,
        #     "type": WidgetTypes.FOLDER,
        #     "text": name,
        #     "parent_uuid": None  # Если появится вложенность папок, сюда будем передавать uuid родителя
        # })
        self.state.add_folder_descriptor(folder_uuid, name, None)
        self.state.set_modified(True)
        # -----------------------------------------------------------------
        folder_item = QStandardItem(name)
        folder_item.setData(folder_uuid, Qt.ItemDataRole.UserRole)

        self.win.tree_model.appendRow(folder_item)
        return folder_item

    def create_gallery(self):
        parent_item, parent_block_uuid = self._get_active_folder_context()
        name = f'Gallery_{self.win.gallery_count}'
        self.win.gallery_count += 1

        widget_uuid = QUuid.createUuid().toString()

        self.state.add_widget_descriptor(
            widget_uuid=widget_uuid,
            widget_type=WidgetTypes.GALLERY,
            title=name,
            parent_block_uuid=parent_block_uuid,
            settings={"current_image_idx": 0}
        )

        # Вызываем универсальный инстанциатор (передаем индекс 0 для нового окна, показываем сразу)
        self._instantiate_widget(
            widget_uuid=widget_uuid,
            widget_type="gallery",
            title=name,
            parent_block_uuid=parent_block_uuid,
            parent_item=parent_item,
            link_idx=0,
            show_window=True
        )

    def create_table(self):
        parent_item, parent_block_uuid = self._get_active_folder_context()
        name = f'Table_{self.win.table_count}'
        self.win.table_count += 1

        widget_uuid = QUuid.createUuid().toString()
        self.state.add_widget_descriptor(widget_uuid, WidgetTypes.TABLE, name, parent_block_uuid)

        self._instantiate_widget(
            widget_uuid=widget_uuid,
            widget_type="table",
            title=name,
            parent_block_uuid=parent_block_uuid,
            parent_item=parent_item,
            link_idx=0,
            show_window=True
        )

    def create_graph(self):
        parent_item, parent_block_uuid = self._get_active_folder_context()
        name = f'Graph_{self.win.graph_count}'
        self.win.graph_count += 1

        widget_uuid = QUuid.createUuid().toString()
        self.state.add_widget_descriptor(widget_uuid, WidgetTypes.GRAPH, name, parent_block_uuid)

        self._instantiate_widget(
            widget_uuid=widget_uuid,
            widget_type="graph",
            title=name,
            parent_block_uuid=parent_block_uuid,
            parent_item=parent_item,
            link_idx=0,
            show_window=True
        )

    # =========================================================================
    # ВОССТАНОВЛЕНИЕ ИЗ ДЕСКРИПТОРА (Вызывается службой загрузки проекта)
    # =========================================================================

    def restore_window_from_descriptor(self, descriptor: dict, parent_item: QStandardItem):
        """Воссоздает живое окно на основе дескриптора из файла сохранения."""
        # Защита от того, что сам дескриптор может быть None
        descriptor = descriptor or {}

        widget_uuid = descriptor.get("uuid")
        title = descriptor.get("title", "Analysis Window")
        w_type = descriptor.get("type")
        parent_block_uuid = descriptor.get("parent_block_uuid")

        # БЕЗОПАСНОЕ ИЗВЛЕЧЕНИЕ: защищаемся от "settings": null в старых файлах
        settings = descriptor.get("settings") or {}
        link_idx = settings.get("current_image_idx", 0)

        self._instantiate_widget(
            widget_uuid=widget_uuid,
            widget_type=w_type,
            title=title,
            parent_block_uuid=parent_block_uuid,
            parent_item=parent_item,
            link_idx=link_idx,
            show_window=False
        )

    def _instantiate_widget(self, widget_uuid: str, widget_type: str, title: str, parent_block_uuid: str,
                            parent_item: QStandardItem, link_idx: int = 0, show_window: bool = True):
        """Универсальный метод материализации любого ОКТ-окна."""
        if not widget_type:
            print("[Factory Error] Тип виджета не задан (None). Проверьте ключи дескриптора.")
            return

        normalized_type = str(widget_type).lower()
        window_class = self._window_registry.get(normalized_type)

        if not window_class:
            print(f"[Factory Critical] Неизвестный тип виджета для фабрики: {normalized_type}. Пропускаем.")
            return

        widget_window = window_class(
            title,
            link_idx,
            obj_type=normalized_type,
            state=self.state,
            linked=parent_block_uuid,
            parent=None
        )

        widget_window.uuid = widget_uuid
        widget_window._force_close = False
        widget_window.window_closed.connect(self.win.hierarchy_controller.on_widget_window_closed)

        sub_window = self.win.widgets_area.addSubWindow(widget_window)
        sub_window.setWindowTitle(title)

        # БЕЗОПАСНОЕ ИЗВЛЕЧЕНИЕ ДЛЯ WORKSPACE
        workspace = self.state.project_data.get("workspace") or {}
        mdi_positions = workspace.get("mdi_positions") or {}

        if widget_uuid in mdi_positions:
            pos_data = mdi_positions[widget_uuid] or {}
            geom = pos_data.get("geometry")
            if geom and isinstance(geom, list) and len(geom) == 4:
                sub_window.setGeometry(geom[0], geom[1], geom[2], geom[3])
            if pos_data.get("is_maximized"):
                sub_window.showMaximized()

        if show_window:
            sub_window.show()
        else:
            sub_window.hide()

        self.registry.register_widget(widget_uuid, widget_window, sub_window)

        item = QStandardItem(title)
        item.setData(widget_uuid, Qt.ItemDataRole.UserRole)
        parent_item.appendRow(item)

        self.win.file_info.expand(self.win.tree_model.indexFromItem(parent_item))

    def _get_active_folder_context(self):
        """Определяет UUID родительской папки на основе выделения в QTreeView."""
        selected_indexes = self.win.file_info.selectedIndexes()
        if not selected_indexes:
            root_item = self.win.tree_model.invisibleRootItem()
            if root_item.rowCount() > 0:
                first_folder = root_item.child(0)
                return first_folder, first_folder.data(Qt.ItemDataRole.UserRole)
            return root_item, "root_folder_0"

        current_item = self.win.tree_model.itemFromIndex(selected_indexes[0])
        node_uuid = current_item.data(Qt.ItemDataRole.UserRole)

        if "Folder" in current_item.text():
            return current_item, node_uuid
        else:
            parent_item = current_item.parent() or self.win.tree_model.invisibleRootItem()
            parent_uuid = parent_item.data(Qt.ItemDataRole.UserRole) or "root_folder_0"
            return parent_item, parent_uuid
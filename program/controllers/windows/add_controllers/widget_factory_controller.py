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
        """Воссоздает живое окно на основе дескриптора из файла сохранения (Этап 5)."""
        widget_uuid = descriptor.get("uuid")
        title = descriptor.get("title", "Analysis Window")
        w_type = descriptor.get("widget_type")
        parent_block_uuid = descriptor.get("parent_block_uuid")

        metadata = descriptor.get("metadata", {})
        link_name = metadata.get("link_name", title)
        link_idx = metadata.get("link_idx", 0)

        # Полностью перенаправляем в единый метод генерации, но окна НЕ показываем (show_window=False)
        self._instantiate_widget(
            widget_uuid=widget_uuid,
            widget_type=w_type,
            title=link_name,
            parent_block_uuid=parent_block_uuid,
            parent_item=parent_item,
            link_idx=link_idx,
            show_window=False
        )

    # =========================================================================
    # ВНУТРЕННИЕ СЛУЖЕБНЫЕ МЕТОДЫ (ЕДИНЫЙ ПАЙПЛАЙН ЖИЗНЕННОГО ЦИКЛА)
    # =========================================================================

    def _instantiate_widget(self, widget_uuid: str, widget_type: str, title: str, parent_block_uuid: str,
                            parent_item: QStandardItem, link_idx: int = 0, show_window: bool = True):
        """
        ФИКС 4: Универсальный метод материализации любого ОКТ-окна.
        Устраняет дублирование кода между созданием новых окон и реставрацией старых.
        """
        # 1. Извлекаем класс из динамического реестра
        window_class = self._window_registry.get(widget_type)
        if not window_class:
            print(f"[Factory Critical] Неизвестный тип виджета для фабрики: {widget_type}. Пропускаем.")
            return

        # 2. Безопасный спавн окна по вашей точной сигнатуре __init__
        widget_window = window_class(
            title,  # link_name
            link_idx,  # link_idx (всегда числовой индекс слоя или 0)
            obj_type=widget_type,  # obj_type
            state=self.state,  # state (Single Source of Truth)
            linked=parent_block_uuid,  # linked
            parent=None  # parent (QMdiArea сама заберет владение)
        )

        # Контроль закрытия крестиком
        widget_window._force_close = False
        widget_window.window_closed.connect(self.win.hierarchy_controller.on_widget_window_closed)

        # 3. Упаковка в QMdiSubWindow через нативный метод addSubWindow
        sub_window = self.win.widgets_area.addSubWindow(widget_window)
        sub_window.setWindowTitle(title)

        # Управляем видимостью в зависимости от контекста (создание или чтение файла)
        if show_window:
            sub_window.show()
        else:
            sub_window.hide()

        # 4. ФИКС 3: Согласованная регистрация в RuntimeRegistry (используем метод из _instantiate_widget)
        self.registry.register_widget(widget_uuid, widget_window, sub_window)

        # 5. Визуальное добавление узла в дерево QTreeView
        item = QStandardItem(title)
        item.setData(widget_uuid, Qt.ItemDataRole.UserRole)
        parent_item.appendRow(item)

        # Раскрываем родительскую папку в интерфейсе
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
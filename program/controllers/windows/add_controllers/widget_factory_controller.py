from PyQt6 import QtCore
from PyQt6.QtWidgets import QMdiSubWindow
from PyQt6.QtGui import QStandardItem
from PyQt6.QtCore import Qt, QObject, QUuid

from ...widgets.gallery_controller import GalleryWindow
from ...widgets.graph_controller import GraphWindow
from ...widgets.table_controller import TableWindow
from ...small_controllers import Folder, TreeRoles


class WidgetFactoryController(QObject):
    """Отвечает исключительно за генерацию новых папок и окон внутри MDI."""

    def __init__(self, main_window, project_state):
        super().__init__(main_window)
        self.win = main_window
        self.state = project_state

    def create_folder(self, name: str = None) -> QStandardItem:
        if not name:
            name = f'Folder_{self.win.folder_count}'
            self.win.folder_count += 1

        folder_obj = Folder(link_name=name, link_idx=QUuid.createUuid())
        folder_item = QStandardItem(folder_obj.link_name)
        folder_item.setData(folder_obj, TreeRoles.ObjectData)

        self.win.tree_model.appendRow(folder_item)
        return folder_item

    def _get_active_folder_context(self):
        """Определяет, к какой папке прикрепить создаваемый виджет."""
        selected_indexes = self.win.file_info.selectedIndexes()
        current_item = self.win.tree_model.itemFromIndex(selected_indexes[0])
        obj = current_item.data(TreeRoles.ObjectData)

        if obj and getattr(obj, 'obj_type', None) == 'folder':
            return current_item, obj.link_idx
        else:
            parent_item = current_item.parent()
            return parent_item, parent_item.data(TreeRoles.ObjectData).link_idx

    def create_gallery(self):
        parent_item, parent_idx = self._get_active_folder_context()
        name = f'Gallery_{self.win.gallery_count}'
        self.win.gallery_count += 1

        window = GalleryWindow(name, QUuid.createUuid(), 'gallery', self.state, parent_idx, self.win)
        self._bootstrap_mdi_window(window, name, parent_item)

    def create_table(self):
        parent_item, parent_idx = self._get_active_folder_context()
        name = f'Table_{self.win.table_count}'
        self.win.table_count += 1

        window = TableWindow(name, QUuid.createUuid(), 'table', self.state, parent_idx, self.win)
        self._bootstrap_mdi_window(window, name, parent_item)

    def create_graph(self):
        parent_item, parent_idx = self._get_active_folder_context()
        name = f'Graph_{self.win.graph_count}'
        self.win.graph_count += 1

        window = GraphWindow(name, QUuid.createUuid(), 'graph', self.state, parent_idx, self.win)
        self._bootstrap_mdi_window(window, name, parent_item)

    def _bootstrap_mdi_window(self, widget_window, name: str, parent_item: QStandardItem):
        """Общая логика сборки MDI-контейнера и добавления его в дерево."""
        widget_window.window_closed.connect(self.win.hierarchy_controller.on_widget_window_closed)

        sub = QMdiSubWindow()
        sub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        sub.setWidget(widget_window)
        sub.setWindowTitle(name)

        self.win.widgets_area.addSubWindow(sub)
        sub.show()

        item = QStandardItem(name)
        item.setData(widget_window, TreeRoles.ObjectData)
        item.setData(sub, TreeRoles.MdiSubWindow)

        parent_item.appendRow(item)
        self.win.file_info.expand(self.win.tree_model.indexFromItem(parent_item))
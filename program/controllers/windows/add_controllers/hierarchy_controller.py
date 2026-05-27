from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QStandardItem
from PyQt6.QtCore import Qt, QObject, QUuid
from ...small_controllers import TreeRoles

class HierarchyController(QObject):
    """Управляет реакцией дерева, контекстными меню, фильтрацией MDI и удалениями."""
    def __init__(self, main_window, project_state):
        super().__init__(main_window)
        self.win = main_window
        self.state = project_state

        # Подвязываем сигналы UI к поведению контроллера
        self.win.tree_model.itemChanged.connect(self.on_item_changed)
        self.win.file_info.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.win.widgets_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.win.widgets_area.customContextMenuRequested.connect(self.open_mdi_context_menu)

    def open_mdi_context_menu(self, position):
        menu = QMenu()
        create_folder_action = menu.addAction("Create folder")
        create_gallery_action = menu.addAction("Create gallery")
        create_table_action = menu.addAction("Create table")

        action = menu.exec(self.win.mapToGlobal(position))

        if action == create_gallery_action:
            self.win.widget_factory.create_gallery()
        elif action == create_folder_action:
            self.win.widget_factory.create_folder()
        elif action == create_table_action:
            self.win.widget_factory.create_table()

    def on_selection_changed(self, selected, deselected):
        indexes = self.win.file_info.selectedIndexes()
        if not indexes:
            self.ensure_active_folder_selection()
            return

        item = self.win.tree_model.itemFromIndex(indexes[0])
        obj = item.data(TreeRoles.ObjectData)

        if obj and getattr(obj, 'obj_type', None) == 'folder':
            active_folder_idx = obj.link_idx
        else:
            parent_item = item.parent()
            if parent_item:
                active_folder_idx = parent_item.data(TreeRoles.ObjectData).link_idx
            else:
                return

        self.update_widgets_visibility(active_folder_idx)

    def update_widgets_visibility(self, folder_idx: QtCore.QUuid):
        for sub_window in self.win.widgets_area.subWindowList():
            widget = sub_window.widget()
            if widget and hasattr(widget, 'linked'):
                if widget.linked == folder_idx:
                    sub_window.show()
                else:
                    sub_window.hide()

    def ensure_active_folder_selection(self):
        root = self.win.tree_model.invisibleRootItem()
        first_folder_item = None

        for row in range(root.rowCount()):
            child = root.child(row)
            c_obj = child.data(TreeRoles.ObjectData)
            if c_obj and getattr(c_obj, 'obj_type', None) == 'folder':
                first_folder_item = child
                break

        if not first_folder_item:
            first_folder_item = self.win.widget_factory.create_folder("Folder 0")

        new_idx = self.win.tree_model.indexFromItem(first_folder_item)
        self.win.file_info.setCurrentIndex(new_idx)

    def on_item_changed(self, item: QStandardItem):
        obj = item.data(TreeRoles.ObjectData)
        if obj is None:
            return
        new_name = item.text()
        self.win.tree_model.blockSignals(True)
        try:
            if obj.obj_type == 'folder':
                obj.link_name = new_name
            else:
                if hasattr(obj, 'rename'):
                    obj.rename(new_name)
                elif hasattr(obj, 'link_name'):
                    obj.link_name = new_name
                sub_window = item.data(TreeRoles.MdiSubWindow)
                if sub_window:
                    sub_window.setWindowTitle(new_name)
        finally:
            self.win.tree_model.blockSignals(False)

    def on_widget_window_closed(self, widget_obj):
        item = self.find_item_by_idx(widget_obj.link_idx)
        if item:
            parent = item.parent()
            if parent:
                parent.removeRow(item.row())
            else:
                self.win.tree_model.removeRow(item.row())

    def find_item_by_idx(self, link_idx: QtCore.QUuid, parent_item=None) -> QStandardItem | None:
        if parent_item is None:
            parent_item = self.win.tree_model.invisibleRootItem()

        for row in range(parent_item.rowCount()):
            item = parent_item.child(row)
            obj = item.data(TreeRoles.ObjectData)
            if obj and hasattr(obj, 'link_idx') and obj.link_idx == link_idx:
                return item
            found = self.find_item_by_idx(link_idx, item)
            if found:
                return found
        return None

    def on_delete_shortcut_triggered(self):
        selected_indexes = self.win.file_info.selectedIndexes()
        if not selected_indexes:
            return
        item = self.win.tree_model.itemFromIndex(selected_indexes[0])
        if item:
            self.remove_item_safely(item)

    def remove_item_safely(self, item: QStandardItem):
        obj = item.data(TreeRoles.ObjectData)
        if obj is None:
            return

        if obj.obj_type == 'folder':
            reply = QtWidgets.QMessageBox.question(
                self.win, "Confirmation", f"Delete folder '{item.text()}' and all its widgets?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return

            while item.rowCount() > 0:
                self.remove_single_widget_item(item.child(0))

            parent = item.parent()
            if parent:
                parent.removeRow(item.row())
            else:
                self.win.tree_model.removeRow(item.row())
        else:
            reply = QtWidgets.QMessageBox.question(
                self.win, "Confirmation", f"Delete widget '{item.text()}'?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.remove_single_widget_item(item)

    def remove_single_widget_item(self, item: QStandardItem):
        widget_obj = item.data(TreeRoles.ObjectData)
        sub_window = item.data(TreeRoles.MdiSubWindow)

        if widget_obj:
            try:
                widget_obj.window_closed.disconnect(self.on_widget_window_closed)
            except TypeError:
                pass
            widget_obj._force_close = True

        if sub_window:
            sub_window.close()
            sub_window.deleteLater()
        if widget_obj:
            widget_obj.deleteLater()

        parent = item.parent()
        if parent:
            parent.removeRow(item.row())
        else:
            self.win.tree_model.removeRow(item.row())
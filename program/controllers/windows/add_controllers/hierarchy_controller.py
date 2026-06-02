from PyQt6 import QtWidgets, QtCore, sip
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QStandardItem
from PyQt6.QtCore import Qt, QObject
from ....state.project_state.constants import WidgetTypes


class HierarchyController(QObject):
    """
    Управляет реакцией дерева, контекстными меню, фильтрацией MDI и удалениями.
    Использует State-driven подход и единый пайплайн удаления (Этап 9).
    """

    def __init__(self, main_window, project_state):
        super().__init__(main_window)
        self.win = main_window
        self.state = project_state

        self.state.sig_data_reset.connect(self.on_project_data_reset)
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

    # =========================================================================
    # СИНХРОНИЗАЦИЯ ВИДИМОСТИ ОКОН (State-driven)
    # =========================================================================

    def on_selection_changed(self, selected, deselected):
        """Срабатывает при клике на элемент дерева."""
        indexes = self.win.file_info.selectedIndexes()
        if not indexes:
            self.ensure_active_folder_selection()
            return

        item = self.win.tree_model.itemFromIndex(indexes[0])
        uuid_str = item.data(Qt.ItemDataRole.UserRole)

        if not uuid_str:
            return

        widgets_dict = self.state.project_data.get("widgets", {})

        if uuid_str in widgets_dict:
            active_folder_uuid = widgets_dict[uuid_str].get("parent_block_uuid")
        else:
            active_folder_uuid = uuid_str

        if active_folder_uuid:
            self.update_widgets_visibility(active_folder_uuid)

    def update_widgets_visibility(self, folder_uuid: str):
        """Управляет видимостью окон MDI на основе активной папки (UUID)."""
        widgets_dict = self.state.project_data.get("widgets", {})

        for w_uuid, descriptor in widgets_dict.items():
            sub_window = self.win.runtime_registry.get_sub_window(w_uuid)

            if sub_window and not sip.isdeleted(sub_window):
                try:
                    if descriptor.get("parent_block_uuid") == folder_uuid:
                        sub_window.show()
                    else:
                        sub_window.hide()
                except RuntimeError:
                    pass

    def ensure_active_folder_selection(self):
        root = self.win.tree_model.invisibleRootItem()
        hierarchy = self.state.project_data.get("hierarchy", [])

        # Создаем дефолтную папку ТОЛЬКО если в проекте вообще 0 папок (чистый старт)
        if not hierarchy:
            self.win.widget_factory.create_folder("Folder 0")
            hierarchy = self.state.project_data.get("hierarchy", [])

        if not hierarchy:
            return

        target_uuid = hierarchy[0]["uuid"]
        first_folder_item = None

        for row in range(root.rowCount()):
            child = root.child(row)
            if child.data(Qt.ItemDataRole.UserRole) == target_uuid:
                first_folder_item = child
                break

        if not first_folder_item:
            return

        new_idx = self.win.tree_model.indexFromItem(first_folder_item)
        selection_model = self.win.file_info.selectionModel()
        if selection_model:
            selection_model.setCurrentIndex(
                new_idx,
                QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect | QtCore.QItemSelectionModel.SelectionFlag.Rows
            )
        else:
            self.win.file_info.setCurrentIndex(new_idx)

        active_uuid = first_folder_item.data(Qt.ItemDataRole.UserRole)
        if active_uuid:
            self.update_widgets_visibility(active_uuid)

    # =========================================================================
    # ПЕРЕИМЕНОВАНИЕ (Синхронизация UI -> State)
    # =========================================================================

    def on_item_changed(self, item: QStandardItem):
        """Срабатывает при ручном переименовании элемента в QTreeView."""
        uuid_str = item.data(Qt.ItemDataRole.UserRole)
        if not uuid_str:
            return

        new_name = item.text()
        self.win.tree_model.blockSignals(True)

        try:
            widgets_dict = self.state.project_data.get("widgets", {})
            if uuid_str in widgets_dict:
                self.state.update_widget_settings(uuid_str, {})
                widgets_dict[uuid_str]["title"] = new_name

                sub_window = self.win.runtime_registry.get_sub_window(uuid_str)
                if sub_window:
                    sub_window.setWindowTitle(new_name)
            else:
                for folder in self.state.project_data.get("hierarchy", []):
                    if folder["uuid"] == uuid_str:
                        folder["text"] = new_name
                        self.state.set_modified(True)
                        break

            # СИНХРОНИЗАЦИЯ: Изменяем имя внутри вложенного tree_structure (для сохранения на диск)
            if "tree_structure" in self.state.project_data:
                self._update_node_in_tree_structure(self.state.project_data["tree_structure"], uuid_str, new_name)
        finally:
            self.win.tree_model.blockSignals(False)

    # =========================================================================
    # ЭТАП 9 — ЕДИНЫЙ PIPELINE УДАЛЕНИЯ ОБЪЕКТОВ
    # =========================================================================

    def execute_deletion_pipeline(self, uuid_str: str):
        """Централизованный конвейер уничтожения объектов."""
        uuid_str = str(uuid_str)  # <--- ФИКС 1: Принудительное приведение к строке
        print("DELETE UUID =", uuid_str)

        is_widget = uuid_str in self.state.project_data.get("widgets", {})
        if is_widget:
            self.state.remove_widget_descriptor(uuid_str)
        else:
            self.state.project_data["hierarchy"] = [
                f for f in self.state.project_data.get("hierarchy", []) if str(f["uuid"]) != uuid_str
            ]
            self.state.set_modified(True)

        # СИНХРОНИЗАЦИЯ: Удаляем узел из вложенной tree_structure, чтобы он не восстановился при перезаписи
        if "tree_structure" in self.state.project_data:
            self._remove_node_from_tree_structure(self.state.project_data["tree_structure"], uuid_str)

        self.win.runtime_registry.unregister_and_destroy(uuid_str)

        item = self.find_item_by_uuid(uuid_str)
        if item:
            parent = item.parent()
            if parent:
                parent.removeRow(item.row())
            else:
                self.win.tree_model.removeRow(item.row())

    def on_widget_window_closed(self, widget_obj):
        """Каллбэк, срабатывающий при ручном закрытии окна крестиком."""
        uuid_str = getattr(widget_obj, 'uuid', None)

        if not uuid_str:
            link_attr = getattr(widget_obj, 'link_idx', None)
            if link_attr and not isinstance(link_attr, int):
                uuid_str = str(link_attr)

        if uuid_str:
            uuid_str = str(uuid_str)  # <--- ФИКС 2: Принудительное приведение к строке
            widgets_dict = self.state.project_data.get("widgets", {})

            if uuid_str not in widgets_dict:
                print(f"CLOSED: Окно {uuid_str} закрыто через пайплайн дерева. Игнорируем дублирующий вызов.")
                return

            print("CLOSED VALID UUID:", uuid_str)
            self.execute_deletion_pipeline(uuid_str)

    def on_delete_shortcut_triggered(self):
        """Срабатывает по горячей клавише Delete на дереве."""
        selected_indexes = self.win.file_info.selectedIndexes()
        if not selected_indexes:
            return
        item = self.win.tree_model.itemFromIndex(selected_indexes[0])
        if item:
            self.ask_and_remove_item(item)

    def ask_and_remove_item(self, item: QStandardItem):
        """Запрашивает подтверждение и запускает очистку."""
        uuid_str = item.data(Qt.ItemDataRole.UserRole)
        if not uuid_str:
            return

        is_folder = any(f["uuid"] == uuid_str for f in self.state.project_data.get("hierarchy", []))
        if is_folder:
            reply = QtWidgets.QMessageBox.question(
                self.win, "Confirmation", f"Delete folder '{item.text()}' and all its widgets?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return

            while item.rowCount() > 0:
                child_item = item.child(0)
                child_uuid = child_item.data(Qt.ItemDataRole.UserRole)
                if child_uuid:
                    self.execute_deletion_pipeline(child_uuid)

            self.execute_deletion_pipeline(uuid_str)
        else:
            reply = QtWidgets.QMessageBox.question(
                self.win, "Confirmation", f"Delete widget '{item.text()}'?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.execute_deletion_pipeline(uuid_str)

    # =========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ПОИСКА И РЕКУРСИВНОЙ СИНХРОНИЗАЦИИ
    # =========================================================================

    def find_item_by_uuid(self, uuid_str: str, parent_item=None) -> QStandardItem | None:
        """Рекурсивно ищет элемент в QTreeView по строковому UUID."""
        if parent_item is None:
            parent_item = self.win.tree_model.invisibleRootItem()

        for row in range(parent_item.rowCount()):
            item = parent_item.child(row)
            item_uuid = item.data(Qt.ItemDataRole.UserRole)

            if item_uuid and str(item_uuid) == str(uuid_str):
                return item

            found = self.find_item_by_uuid(uuid_str, item)
            if found:
                return found
        return None

    def _update_node_in_tree_structure(self, node: dict, target_uuid: str, new_text: str) -> bool:
        """Рекурсивно ищет узел в дереве метаданных и правит текстовый заголовок."""
        if node.get("uuid") == target_uuid:
            node["text"] = new_text
            return True
        if "children" in node:
            for child in node["children"]:
                if self._update_node_in_tree_structure(child, target_uuid, new_text):
                    return True
        return False

    def _remove_node_from_tree_structure(self, node: dict, target_uuid: str) -> bool:
        """Рекурсивно находит узел в дереве метаданных и вырезает его из массива детей."""
        if "children" in node:
            for idx, child in enumerate(node["children"]):
                if child.get("uuid") == target_uuid:
                    node["children"].pop(idx)
                    return True
                if self._remove_node_from_tree_structure(child, target_uuid):
                    return True
        return False

    @QtCore.pyqtSlot()
    def on_project_data_reset(self):
        """
        Вызывается реактивно ТОЛЬКО при создании абсолютно нового проекта из кода приложения.
        """
        self.win.file_info.setUpdatesEnabled(False)

        sel_model = self.win.file_info.selectionModel()
        if sel_model:
            sel_model.blockSignals(True)

        # ЗАЩИТА: Блокируем сигналы модели на время построения "дефолтного" проекта
        self.win.tree_model.blockSignals(True)

        try:
            self.win.tree_model.clear()
            self.win.tree_model.setHorizontalHeaderLabels(["Project tree"])

            folder_items = {}
            hierarchy_list = self.state.project_data.get("hierarchy") or []

            for folder_data in hierarchy_list:
                folder_data = folder_data or {}
                uuid_str = folder_data.get("uuid")
                text = folder_data.get("text", "Folder")

                if not uuid_str:
                    continue

                folder_item = QStandardItem(text)
                folder_item.setData(uuid_str, Qt.ItemDataRole.UserRole)
                self.win.tree_model.appendRow(folder_item)
                folder_items[uuid_str] = folder_item

            widgets_dict = self.state.project_data.get("widgets") or []
            for w_uuid, descriptor in widgets_dict.items():
                descriptor = descriptor or {}
                parent_uuid = descriptor.get("parent_block_uuid")
                parent_folder_item = folder_items.get(parent_uuid)

                if parent_folder_item:
                    self.win.widget_factory.restore_window_from_descriptor(descriptor, parent_folder_item)

        finally:
            self.win.tree_model.blockSignals(False)
            if sel_model:
                sel_model.blockSignals(False)
            self.win.file_info.setUpdatesEnabled(True)

        if hasattr(self.win, 'file_info'):
            self.win.file_info.expandAll()
        self.ensure_active_folder_selection()
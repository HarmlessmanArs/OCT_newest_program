from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QStandardItem
from PyQt6.QtCore import Qt, QObject, QUuid
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

        # Проверяем по State: это виджет или папка?
        widgets_dict = self.state.project_data.get("widgets", {})

        if uuid_str in widgets_dict:
            # Кликнули на виджет -> берем UUID его родительской папки
            active_folder_uuid = widgets_dict[uuid_str].get("parent_block_uuid")
        else:
            # Кликнули на папку -> она и есть активный контекст
            active_folder_uuid = uuid_str

        if active_folder_uuid:
            self.update_widgets_visibility(active_folder_uuid)

    def update_widgets_visibility(self, folder_uuid: str):
        """Управляет видимостью окон MDI на основе активной папки (UUID)."""
        widgets_dict = self.state.project_data.get("widgets", {})

        for w_uuid, descriptor in widgets_dict.items():
            # Запрашиваем живое MDI-окно из нашего нового Runtime Registry
            sub_window = self.win.runtime_registry.get_sub_window(w_uuid)
            if sub_window:
                # Если родитель окна совпадает с выбранной папкой — показываем
                if descriptor.get("parent_block_uuid") == folder_uuid:
                    sub_window.show()
                else:
                    sub_window.hide()

    def ensure_active_folder_selection(self):
        root = self.win.tree_model.invisibleRootItem()
        first_folder_item = None

        # Собираем UUID всех папок из честного State
        folder_uuids = {f["uuid"] for f in self.state.project_data.get("hierarchy", []) if
                        f["type"] == WidgetTypes.FOLDER}

        for row in range(root.rowCount()):
            child = root.child(row)
            uuid_str = child.data(Qt.ItemDataRole.UserRole)
            # ТЕПЕРЬ ПРОВЕРКА СТРОГАЯ:
            if uuid_str in folder_uuids:
                first_folder_item = child
                break

        if not first_folder_item:
            first_folder_item = self.win.widget_factory.create_folder("Folder 0")

        new_idx = self.win.tree_model.indexFromItem(first_folder_item)
        self.win.file_info.setCurrentIndex(new_idx)

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
                # 1. Обновляем имя в дескрипторе State
                self.state.update_widget_settings(uuid_str, {})  # триггерит modified=True
                widgets_dict[uuid_str]["title"] = new_name

                # 2. Обновляем заголовок живого MDI-окна через Registry
                sub_window = self.win.runtime_registry.get_sub_window(uuid_str)
                if sub_window:
                    sub_window.setWindowTitle(new_name)
            else:
                # Это папка, обновляем её в иерархии (Этап 3)
                for folder in self.state.project_data.get("hierarchy", []):
                    if folder["uuid"] == uuid_str:
                        folder["text"] = new_name
                        self.state.set_modified(True)
                        break
        finally:
            self.win.tree_model.blockSignals(False)

    # =========================================================================
    # ЭТАП 9 — ЕДИНЫЙ PIPELINE УДАЛЕНИЯ ОБЪЕКТОВ
    # =========================================================================

    def execute_deletion_pipeline(self, uuid_str: str):
        """
        Централизованный конвейер уничтожения объектов.
        Удаляет сущность отовсюду синхронно и безопасно.
        """
        # --- Шаг 1. Delete from State ---
        is_widget = uuid_str in self.state.project_data.get("widgets", {})
        if is_widget:
            self.state.remove_widget_descriptor(uuid_str)
        else:
            # Удаление папки из hierarchy данных
            self.state.project_data["hierarchy"] = [
                f for f in self.state.project_data.get("hierarchy", []) if f["uuid"] != uuid_str
            ]
            self.state.set_modified(True)

        # --- Шаг 2, 4, 5. Delete Runtime Widget, MDI Window & Cleanup Registry ---
        # Наш новый RuntimeRegistry делает всю эту магию одной командой!
        self.win.runtime_registry.unregister_and_destroy(uuid_str)

        # --- Шаг 3. Remove Tree Item ---
        item = self.find_item_by_uuid(uuid_str)
        if item:
            parent = item.parent()
            if parent:
                parent.removeRow(item.row())
            else:
                self.win.tree_model.removeRow(item.row())

    def on_widget_window_closed(self, widget_obj):
        """Каллбэк, срабатывающий при ручном закрытии окна крестиком."""
        # Вытаскиваем строковый UUID, который виджет хранит у себя
        uuid_attr = getattr(widget_obj, 'link_idx', None) or getattr(widget_obj, 'uuid', None)
        if uuid_attr:
            uuid_str = str(uuid_attr)
            # Запускаем конвейер удаления
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

        # is_widget = uuid_str in self.state.project_data.get("widgets", {})
        is_folder = any(f["uuid"] == uuid_str and f["type"] == WidgetTypes.FOLDER for f in
                        self.state.project_data.get("hierarchy", []))
        if is_folder:
            # Удаление папки
            reply = QtWidgets.QMessageBox.question(
                self.win, "Confirmation", f"Delete folder '{item.text()}' and all its widgets?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return

            # Сначала каскадно удаляем все вложенные виджеты через пайплайн
            while item.rowCount() > 0:
                child_item = item.child(0)
                child_uuid = child_item.data(Qt.ItemDataRole.UserRole)
                if child_uuid:
                    self.execute_deletion_pipeline(child_uuid)

            # Теперь удаляем саму папку
            self.execute_deletion_pipeline(uuid_str)
        else:
            # Удаление одиночного виджета
            reply = QtWidgets.QMessageBox.question(
                self.win, "Confirmation", f"Delete widget '{item.text()}'?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.execute_deletion_pipeline(uuid_str)

    # =========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ПОИСКА
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
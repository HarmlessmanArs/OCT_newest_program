from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QMdiSubWindow, QMenu
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction, QKeySequence
from PyQt6.QtCore import Qt

# Импорты из вашей структуры проекта
from ...gui.windows import Ui_MainWindow
from ..widgets.gallery_controller import GalleryWindow
from ..widgets.graph_controller import GraphWindow
from ..widgets.table_controller import TableWindow
from ..small_controllers import Folder, TreeRoles
from ...state.project_state.state import ProjectState


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)  # Инициализируем компоненты из Designer (.ui)

        # Данные по проекту
        self.app_name = 'OCT project'
        self.setWindowTitle(f"[New project] — {self.app_name}")

        self.project_state = ProjectState()
        self.project_state.sig_modified_changed.connect(self._update_window_title)
        self.project_state.sig_project_path_changed.connect(self._update_window_title)
        self.project_state.sig_data_reset.connect(self._on_project_reset)

        # Настройка модели дерева проектов
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Project Files"])
        self.file_info.setModel(self.tree_model)

        self.tree_model.itemChanged.connect(self.on_item_changed)

        # НАСТРОЙКА: Отслеживание кликов/выбора элементов в дереве для фильтрации окон
        self.file_info.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # Настройка контекстного меню для MDI-области
        self.widgets_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.widgets_area.customContextMenuRequested.connect(self.open_mdi_context_menu)

        # Хоткей Delete для удаления элементов из дерева
        self.delete_action = QAction(self)
        self.delete_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self.delete_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.delete_action.triggered.connect(self.on_delete_shortcut_triggered)
        self.file_info.addAction(self.delete_action)

        # УСЛОВИЕ (а): Изначально создаем и выделяем стартовую папку
        init_folder = self.create_folder("Folder 0")
        init_index = self.tree_model.indexFromItem(init_folder)
        self.file_info.setCurrentIndex(init_index)

        self.folder_count = 1
        self.gallery_count = 1
        self.graph_count = 1
        self.table_count = 1

    def _update_window_title(self):
        path = self.project_state.current_path
        project_name = path.name if path else "New project"
        marker = " *" if self.project_state.modified else ""
        self.setWindowTitle(f"[{project_name}]{marker} — {self.app_name}")

    def _on_project_reset(self):
        # Очищаем виджеты главного окна
        pass

    def open_mdi_context_menu(self, position):
        """Контекстное меню MDI-области."""
        menu = QMenu()
        create_folder_action = menu.addAction("Create folder")
        create_gallery_action = menu.addAction("Create gallery")
        create_table_action = menu.addAction("Create table")

        action = menu.exec(self.mapToGlobal(position))

        if action == create_gallery_action:
            self.create_gallery()
        elif action == create_folder_action:
            self.create_folder()
        elif action == create_table_action:
            self.create_table()

    # =========================================================================
    # ЛОГИКА ФИЛЬТРАЦИИ И ОПРЕДЕЛЕНИЯ АКТИВНОЙ ПАПКИ
    # =========================================================================

    def on_selection_changed(self, selected, deselected):
        """Слот: Вызывается автоматически при смене выбора в дереве проекта."""
        indexes = self.file_info.selectedIndexes()

        # Гарантия того, что папка ВСЕГДА выбрана. Если выбор пропал (например, стерли элемент)
        if not indexes:
            self.ensure_active_folder_selection()
            return

        item = self.tree_model.itemFromIndex(indexes[0])
        obj = item.data(TreeRoles.ObjectData)

        # Находим UUID папки, которой принадлежат отображаемые виджеты
        if obj and getattr(obj, 'obj_type', None) == 'folder':
            active_folder_idx = obj.link_idx
        else:
            parent_item = item.parent()
            if parent_item:
                active_folder_idx = parent_item.data(TreeRoles.ObjectData).link_idx
            else:
                return

        # Запускаем обновление видимости окон в MDI-зоне
        self.update_widgets_visibility(active_folder_idx)

    def update_widgets_visibility(self, folder_idx: QtCore.QUuid):
        """Переключает видимость окон в зависимости от выбранной папки."""
        for sub_window in self.widgets_area.subWindowList():
            widget = sub_window.widget()
            # Проверяем наличие атрибута 'linked' (это свойство LinkBase у всех WidgetsWindow)
            if widget and hasattr(widget, 'linked'):
                if widget.linked == folder_idx:
                    sub_window.show()  # Показываем окна текущей папки
                else:
                    sub_window.hide()  # Скрываем окна чужих папок

    def ensure_active_folder_selection(self):
        """Вспомогательный метод обеспечения безопасности: гарантирует постоянный выбор."""
        root = self.tree_model.invisibleRootItem()
        first_folder_item = None

        # Ищем первую попавшуюся папку в корне дерева
        for row in range(root.rowCount()):
            child = root.child(row)
            c_obj = child.data(TreeRoles.ObjectData)
            if c_obj and getattr(c_obj, 'obj_type', None) == 'folder':
                first_folder_item = child
                break

        # Если папок вообще не осталось во всем проекте, принудительно создаем новую стартовую
        if not first_folder_item:
            first_folder_item = self.create_folder("Folder 0")

        # Программно устанавливаем фокус на эту папку
        new_idx = self.tree_model.indexFromItem(first_folder_item)
        self.file_info.setCurrentIndex(new_idx)

    # =========================================================================
    # ОСТАЛЬНАЯ ИСПРАВЛЕННАЯ СИСТЕМНАЯ ЛОГИКА (БЕЗ ДУБЛИРУЮЩИХ ОКОН)
    # =========================================================================

    def on_item_changed(self, item: QStandardItem):
        obj = item.data(TreeRoles.ObjectData)
        if obj is None:
            return
        new_name = item.text()
        self.tree_model.blockSignals(True)
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
            self.tree_model.blockSignals(False)

    def on_widget_window_closed(self, widget_obj):
        item = self.find_item_by_idx(widget_obj.link_idx)
        if item:
            parent = item.parent()
            if parent:
                parent.removeRow(item.row())
            else:
                self.tree_model.removeRow(item.row())

    def find_item_by_idx(self, link_idx: QtCore.QUuid, parent_item=None) -> QStandardItem | None:
        if parent_item is None:
            parent_item = self.tree_model.invisibleRootItem()

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
        selected_indexes = self.file_info.selectedIndexes()
        if not selected_indexes:
            return

        item = self.tree_model.itemFromIndex(selected_indexes[0])
        if item:
            self.remove_item_safely(item)

    def remove_item_safely(self, item: QStandardItem):
        obj = item.data(TreeRoles.ObjectData)
        if obj is None:
            return

        if obj.obj_type == 'folder':
            reply = QtWidgets.QMessageBox.question(
                self, "Confirmation",
                f"Delete folder '{item.text()}' and all its widgets?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return

            while item.rowCount() > 0:
                child_item = item.child(0)
                self.remove_single_widget_item(child_item)

            parent = item.parent()
            if parent:
                parent.removeRow(item.row())
            else:
                self.tree_model.removeRow(item.row())

        else:
            reply = QtWidgets.QMessageBox.question(
                self, "Confirmation",
                f"Delete widget '{item.text()}'?",
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
            self.tree_model.removeRow(item.row())

    def create_folder(self, name: str = None) -> QStandardItem:
        """Создает сущность папки и добавляет её в корень дерева проекта."""
        if not name:
            name = f'Folder_{self.folder_count}'
            self.folder_count += 1

        folder_obj = Folder(link_name=name, link_idx=QtCore.QUuid.createUuid())
        folder_item = QStandardItem(folder_obj.link_name)
        folder_item.setData(folder_obj, TreeRoles.ObjectData)

        self.tree_model.appendRow(folder_item)
        return folder_item

    def create_gallery(self):
        """Создает галерею строго внутри текущей активной папки."""
        # УСЛОВИЕ (б): Так как папка выбрана ВСЕГДА, берем текущий индекс без лишних проверок
        selected_indexes = self.file_info.selectedIndexes()
        current_item = self.tree_model.itemFromIndex(selected_indexes[0])
        obj = current_item.data(TreeRoles.ObjectData)

        # Если выбран виджет, его родителем в дереве является папка
        if obj and getattr(obj, 'obj_type', None) == 'folder':
            parent_item = current_item
            parent_idx = obj.link_idx
        else:
            parent_item = current_item.parent()
            parent_idx = parent_item.data(TreeRoles.ObjectData).link_idx

        gallery_name = f'Gallery_{self.gallery_count}'
        self.gallery_count += 1

        gallery_window = GalleryWindow(
            link_name=gallery_name,
            link_idx=QtCore.QUuid.createUuid(),
            obj_type='gallery',
            state=self.project_state,
            linked=parent_idx,  # Связываем виджет с уникальным UUID папки
            parent=self
        )
        print(gallery_window.__dict__)
        gallery_window.window_closed.connect(self.on_widget_window_closed)

        sub = QMdiSubWindow()
        sub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        sub.setWidget(gallery_window)
        sub.setWindowTitle(gallery_name)
        self.widgets_area.addSubWindow(sub)

        # Показываем окно только если оно создано в текущей просматриваемой папке
        sub.show()

        gallery_item = QStandardItem(gallery_name)
        gallery_item.setData(gallery_window, TreeRoles.ObjectData)
        gallery_item.setData(sub, TreeRoles.MdiSubWindow)

        parent_item.appendRow(gallery_item)
        self.file_info.expand(self.tree_model.indexFromItem(parent_item))

    def create_table(self):
        """Создает галерею строго внутри текущей активной папки."""
        # УСЛОВИЕ (б): Так как папка выбрана ВСЕГДА, берем текущий индекс без лишних проверок
        selected_indexes = self.file_info.selectedIndexes()
        current_item = self.tree_model.itemFromIndex(selected_indexes[0])
        obj = current_item.data(TreeRoles.ObjectData)

        # Если выбран виджет, его родителем в дереве является папка
        if obj and getattr(obj, 'obj_type', None) == 'folder':
            parent_item = current_item
            parent_idx = obj.link_idx
        else:
            parent_item = current_item.parent()
            parent_idx = parent_item.data(TreeRoles.ObjectData).link_idx

        table_name = f'Table_{self.table_count}'
        self.table_count += 1

        table_window = TableWindow(
            link_name=table_name,
            link_idx=QtCore.QUuid.createUuid(),
            obj_type='table',
            state=self.project_state,
            linked=parent_idx,  # Связываем виджет с уникальным UUID папки
            parent=self
        )

        table_window.window_closed.connect(self.on_widget_window_closed)

        sub = QMdiSubWindow()
        sub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        sub.setWidget(table_window)
        sub.setWindowTitle(table_name)
        self.widgets_area.addSubWindow(sub)

        # Показываем окно только если оно создано в текущей просматриваемой папке
        sub.show()

        table_item = QStandardItem(table_name)
        table_item.setData(table_window, TreeRoles.ObjectData)
        table_item.setData(sub, TreeRoles.MdiSubWindow)

        parent_item.appendRow(table_item)
        self.file_info.expand(self.tree_model.indexFromItem(parent_item))

    def create_graph(self):
        """Создает галерею строго внутри текущей активной папки."""
        # УСЛОВИЕ (б): Так как папка выбрана ВСЕГДА, берем текущий индекс без лишних проверок
        selected_indexes = self.file_info.selectedIndexes()
        current_item = self.tree_model.itemFromIndex(selected_indexes[0])
        obj = current_item.data(TreeRoles.ObjectData)

        # Если выбран виджет, его родителем в дереве является папка
        if obj and getattr(obj, 'obj_type', None) == 'folder':
            parent_item = current_item
            parent_idx = obj.link_idx
        else:
            parent_item = current_item.parent()
            parent_idx = parent_item.data(TreeRoles.ObjectData).link_idx

        graph_name = f'Graph_{self.graph_count}'
        self.graph_count += 1

        graph_window = GraphWindow(
            link_name=graph_name,
            link_idx=QtCore.QUuid.createUuid(),
            obj_type='graph',
            state=self.project_state,
            linked=parent_idx,  # Связываем виджет с уникальным UUID папки
            parent=self
        )

        graph_window.window_closed.connect(self.on_widget_window_closed)

        sub = QMdiSubWindow()
        sub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        sub.setWidget(graph_window)
        sub.setWindowTitle(graph_name)
        self.widgets_area.addSubWindow(sub)

        # Показываем окно только если оно создано в текущей просматриваемой папке
        sub.show()

        graph_item = QStandardItem(graph_name)
        graph_item.setData(graph_window, TreeRoles.ObjectData)
        graph_item.setData(sub, TreeRoles.MdiSubWindow)

        parent_item.appendRow(graph_item)
        self.file_info.expand(self.tree_model.indexFromItem(parent_item))
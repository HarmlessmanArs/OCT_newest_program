from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QMdiSubWindow, QMenu
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction, QKeySequence
from PyQt6.QtCore import Qt

# Импорты из вашей структуры проекта
from ...gui.windows import Ui_MainWindow
from ..widgets.gallery_controller import GalleryWindow
from ..small_controllers import Folder, TreeRoles


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)  # Инициализируем компоненты из Designer (.ui)
        self.setWindowTitle("Main window")

        self.folder_count = 1
        self.gallery_count = 1

        # Настройка модели дерева проектов
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Project Files"])
        self.file_info.setModel(self.tree_model)

        self.tree_model.itemChanged.connect(self.on_item_changed)

        # Настройка контекстного меню для MDI-области
        self.widgets_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.widgets_area.customContextMenuRequested.connect(self.open_mdi_context_menu)

        # Настройка для удаления элемента из дерева
        self.delete_action = QAction(self)
        self.delete_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self.delete_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.delete_action.triggered.connect(self.on_delete_shortcut_triggered)
        self.file_info.addAction(self.delete_action)

    def on_item_changed(self, item: QStandardItem):
        """Слот, срабатывающий при редактировании текста элемента в дереве проектов."""
        obj = item.data(TreeRoles.ObjectData)
        if obj is None:
            return
        new_name = item.text()
        # Блокируем сигналы модели на время обновления, чтобы избежать бесконечной рекурсии
        self.tree_model.blockSignals(True)
        try:
            if obj.obj_type == 'folder':
                # Логика только для папки
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

    def open_mdi_context_menu(self, position):
        menu = QMenu()
        create_action = menu.addAction("Create gallery")
        action = menu.exec(self.mapToGlobal(position))

        if action == create_action:
            self.create_gallery()

    ### Удаление виджета, а потом из дерева

    def on_widget_window_closed(self, widget_obj):
        """Слот: Окно было закрыто пользователем через интерфейс (крестик).
        Удаляем соответствующий элемент из дерева проекта."""
        item = self.find_item_by_object(widget_obj)
        if item:
            parent = item.parent()
            if parent:
                parent.removeRow(item.row())
            else:
                self.tree_model.removeRow(item.row())

    def find_item_by_object(self, obj, parent_item=None) -> QStandardItem | None:
        """Рекурсивный поиск элемента QStandardItem внутри tree_model по ссылке на объект."""
        if parent_item is None:
            parent_item = self.tree_model.invisibleRootItem()

        for row in range(parent_item.rowCount()):
            item = parent_item.child(row)
            if item.data(TreeRoles.ObjectData) == obj:
                return item

            # Если это папка, ищем глубже внутри неё
            found = self.find_item_by_object(obj, item)
            if found:
                return found
        return None


    # Удаление из дерева, а затем виджета

    def on_delete_shortcut_triggered(self):
        """Слот: Пользователь нажал клавишу Delete на дереве проектов."""
        selected_indexes = self.file_info.selectedIndexes()
        if not selected_indexes:
            return

        item = self.tree_model.itemFromIndex(selected_indexes[0])
        if item:
            self.remove_item_safely(item)

    def remove_item_safely(self, item: QStandardItem):
        """Метод запроса подтверждения и каскадного удаления элементов."""
        obj = item.data(TreeRoles.ObjectData)
        if obj is None:
            return

        if obj.obj_type == 'folder':
            # Запрос подтверждения на удаление папки целиком
            reply = QtWidgets.QMessageBox.question(
                self, "Confirmation",
                f"Delete folder '{item.text()}' and all its widgets?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return

            # Сначала рекурсивно закрываем и очищаем все вложенные виджеты
            while item.rowCount() > 0:
                child_item = item.child(0)
                self.remove_single_widget_item(child_item)

            # Удаляем саму пустую папку из корня дерева
            parent = item.parent()
            if parent:
                parent.removeRow(item.row())
            else:
                self.tree_model.removeRow(item.row())

        else:
            # Запрос подтверждения на удаление одного конкретного виджета
            reply = QtWidgets.QMessageBox.question(
                self, "Confirmation",
                f"Delete widget '{item.text()}'?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.remove_single_widget_item(item)

    def remove_single_widget_item(self, item: QStandardItem):
        """Внутренний метод: физически уничтожает окно в MDI и строку в дереве."""
        widget_obj = item.data(TreeRoles.ObjectData)
        sub_window = item.data(TreeRoles.MdiSubWindow)

        if widget_obj:
            # Отключаем сигнал закрытия, чтобы не вызвать зацикливание удаления из дерева
            try:
                widget_obj.window_closed.disconnect(self.on_widget_window_closed)
            except TypeError:
                pass

            # Активируем флаг принудительного закрытия без вызова диалогов QMessageBox
            widget_obj._force_close = True

        # Закрываем и уничтожаем контейнер MDI-окна
        if sub_window:
            sub_window.close()
            sub_window.deleteLater()

        if widget_obj:
            widget_obj.deleteLater()

        # Вырезаем элемент из дерева
        parent = item.parent()
        if parent:
            parent.removeRow(item.row())
        else:
            self.tree_model.removeRow(item.row())

    # Создание окон

    def create_folder(self, name: str = None) -> QStandardItem:
        """Создает сущность папки и добавляет её в корень дерева проекта."""
        if not name:
            name = f'Folder_{self.folder_count}'
            self.folder_count += 1

        folder_obj = Folder(link_name=name, link_idx=QtCore.QUuid.createUuid())
        print(folder_obj.__dict__)
        folder_item = QStandardItem(folder_obj.link_name)
        folder_item.setData(folder_obj, TreeRoles.ObjectData)

        self.tree_model.appendRow(folder_item)
        return folder_item

    def create_gallery(self):
        """Создает галерею в выбранной папке дерева или в новой автоматической папке."""
        # 1. Пытаемся определить текущую выбранную папку в дереве `file_info`
        selected_indexes = self.file_info.selectedIndexes()
        parent_item = None
        parent_idx = None

        if selected_indexes:
            current_item = self.tree_model.itemFromIndex(selected_indexes[0])
            obj = current_item.data(TreeRoles.ObjectData)
            if obj and getattr(obj, 'obj_type', None) == 'folder':
                parent_item = current_item
                parent_idx = obj.link_idx

        # Если папка не выбрана, создаем новую
        if parent_item is None:
            parent_item = self.create_folder()
            parent_idx = parent_item.data(TreeRoles.ObjectData).link_idx

        # 2. Создаем окно галереи
        gallery_name = f'Gallery_{self.gallery_count}'
        self.gallery_count += 1

        gallery_window = GalleryWindow(
            link_name=gallery_name,
            link_idx=QtCore.QUuid.createUuid(),
            obj_type='gallery',
            linked=parent_idx,  # Привязываем честный QUuid папки
            parent=self
        )
        print(gallery_window.__dict__)
        # 3. Добавляем окно в MDI-область `widgets_area`
        sub = QMdiSubWindow()
        # sub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        sub.setWidget(gallery_window)
        sub.setWindowTitle(gallery_name)
        self.widgets_area.addSubWindow(sub)
        sub.show()

        # 4. Создаем элемент дерева и связываем метаданные
        gallery_item = QStandardItem(gallery_name)
        gallery_item.setData(gallery_window, TreeRoles.ObjectData)
        gallery_item.setData(sub, TreeRoles.MdiSubWindow)

        # Добавляем галерею в папку и раскрываем её в интерфейсе
        parent_item.appendRow(gallery_item)
        self.file_info.expand(self.tree_model.indexFromItem(parent_item))

    def create_table(self):
        pass

    def create_graph(self):
        pass
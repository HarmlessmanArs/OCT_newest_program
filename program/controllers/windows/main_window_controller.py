from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QMdiSubWindow, QMenu
from PyQt6.QtGui import QStandardItemModel, QStandardItem
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

    def open_mdi_context_menu(self, position):
        menu = QMenu()
        create_action = menu.addAction("Create gallery")
        action = menu.exec(self.mapToGlobal(position))

        if action == create_action:
            self.create_gallery()

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

    def create_table(self):
        pass

    def create_graph(self):
        pass
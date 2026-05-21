from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QMenu, QMdiArea, QMdiSubWindow
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt
from ...gui.windows import Ui_MainWindow
from ..widgets.gallery_controller import GalleryWindow


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()

        # self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # self.customContextMenuRequested.connect(self.open_context_menu)

        # self.ui = Ui_MainWindow()
        self.setupUi(self)
        self.setWindowTitle("Main window")

        self.folder_names: list = []

        self.folder_count = 1
        self.gallery_count = 1

        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Project Files"])
        self.file_info.setModel(self.tree_model)
        self.tree_model.itemChanged.connect(self.on_item_changed)

        self.widgets_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.widgets_area.customContextMenuRequested.connect(self.open_mdi_context_menu)


    def open_mdi_context_menu(self, position):
        menu = QMenu()
        create_action = menu.addAction("Create gallery")
        action = menu.exec(self.mapToGlobal(position))

        if action == create_action:
            self.create_gallery()

    def create_gallery(self):
        gallery_name = f'Gallery_{self.gallery_count}'
        gallery_window = GalleryWindow(link_name=gallery_name,
                                       link_idx=QtCore.QUuid.createUuid(),
                                       obj_type='gallery',
                                       linked=None,
                                       parent=self)
        print(gallery_window.__dict__)
        sub = QMdiSubWindow()
        sub.setWidget(gallery_window)

        self.widgets_area.addSubWindow(sub)
        sub.show()

        self.gallery_count += 1

        #folder

        folder_name = f'Folder_{self.folder_count}'
        folder_item = QStandardItem(folder_name)  # Создаем папку

        gallery_item = QStandardItem(gallery_name)  # Создаем элемент галереи

        # Сохраняем ссылку на sub-окно внутрь элемента галереи.
        # Это нужно, чтобы при переименовании знать, какое именно окно менять.
        gallery_item.setData(gallery_window, Qt.ItemDataRole.UserRole + 1)
        gallery_item.setData(sub, Qt.ItemDataRole.UserRole + 2)

        # Выстраиваем иерархию: Папка -> Галерея
        folder_item.appendRow(gallery_item)
        self.tree_model.appendRow(folder_item)

        # Раскрываем папку по умолчанию, чтобы пользователь сразу видел галерею
        self.file_info.expand(self.tree_model.indexFromItem(folder_item))
        self.folder_count += 1

    @staticmethod
    def on_item_changed(item: QStandardItem):
        # 1. Достаем наш объект GalleryWindow
        gallery_obj = item.data(Qt.ItemDataRole.UserRole + 1)

        # 2. Достаем контейнер QMdiSubWindow (чтобы поменять заголовок рамки)
        # sub_window = item.data(Qt.ItemDataRole.UserRole + 2)

        if gallery_obj is not None:
            new_name = item.text()

            # Вызываем ваш метод: меняется и self.name, и заголовок внутреннего виджета
            gallery_obj.rename(new_name)
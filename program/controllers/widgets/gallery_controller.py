from pathlib import Path
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt6.QtCore import Qt, QSize, QUuid

from program.gui.windows import Ui_Form_gallery
from .widgets_controller import WidgetsWindow
from ..small_controllers import UuidController, ImageObj


class GalleryWindow(WidgetsWindow):
    def __init__(self, link_name, link_idx, obj_type='gallery', state=None, linked=None, parent=None):
        super().__init__(link_name, link_idx, obj_type, state, linked, parent)
        self.setWindowFlag(Qt.WindowType.Window)

        self.ui = Ui_Form_gallery()
        self.ui.setupUi(self)
        self.setWindowTitle(link_name)

        # 1. Инициализируем модель данных для QListView
        self.images_model = QStandardItemModel(self)
        self.ui.gallery_view.setModel(self.images_model)

        # 2. Настраиваем QListView, чтобы он выглядел как галерея (плиткой)
        self.ui.gallery_view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.ui.gallery_view.setIconSize(QSize(100, 100))  # Размер иконок
        self.ui.gallery_view.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.ui.gallery_view.setSpacing(10)  # Отступы между картинками
        self.ui.gallery_view.setWordWrap(True)  # Перенос длинных названий файлов

        # 3. Подключаем кнопку "Load images"
        self.ui.load_imageButton.clicked.connect(self.load_images)

        # Локальный словарь для хранения объектов изображений
        # В будущем этот словарь будет синхронизироваться со State (datablocks)
        self.loaded_images = {}

    def load_images(self):
        """Открывает диалог выбора файлов и загружает их в галерею."""
        # Открываем диалог. Расширения берем из дизайн-проекта (SAVE.md)
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images",
            "",
            "Images (*.tiff *.tif *.png *.jpg *.jpeg *.bmp)"
        )

        if not file_paths:
            return

        # Родительский UUID (наша текущая галерея)
        parent_uuid = self.link_idx

        for path_str in file_paths:
            path = Path(path_str)

            # Генерируем новый UUID для картинки и очищаем его
            raw_uuid = QUuid.createUuid()
            img_uuid = UuidController.clean_uuid(raw_uuid)

            # 1. Создаем объект бизнес-логики (ImageObj)
            img_obj = ImageObj(
                link_name=path.name,
                link_idx=img_uuid,
                linked=parent_uuid,
                file_path=str(path)
            )
            self.loaded_images[img_uuid] = img_obj

            # 2. Создаем визуальный элемент для QListView
            item = QStandardItem(path.name)

            # Подгружаем картинку как иконку (Qt сам ее сожмет до размеров setIconSize)
            item.setIcon(QIcon(str(path)))

            # Сохраняем чистый UUID картинки внутрь элемента интерфейса
            item.setData(img_uuid, Qt.ItemDataRole.UserRole)

            # Добавляем элемент в модель
            self.images_model.appendRow(item)

        # Опционально: можно добавить вывод в статус-бар о загрузке
        print(f"[GALLERY] Загружено {len(file_paths)} изображений. Всего: {self.images_model.rowCount()}")
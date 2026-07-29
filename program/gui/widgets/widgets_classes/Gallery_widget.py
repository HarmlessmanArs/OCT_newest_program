import os
from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtWidgets import (QFileDialog, QDialog, QAbstractItemView, QMessageBox)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon, QPixmap

from ..base_widget import BaseProjectWidget
from ...windows.ui_gallery_window import Ui_Form_gallery
from ...additional_windows.ui_data_info import Ui_Form_data_info


class DataInfoDialog(QDialog):
    """Класс-обертка для окна Data Info"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Form_data_info()
        self.ui.setupUi(self)
        self.setWindowTitle("Data Info")

        # Подключаем логику: при изменении галочки "Is RI known?"
        self.ui.checkBox.toggled.connect(self.on_ri_toggled)

        # Принудительно вызываем метод при инициализации,
        # чтобы установить правильное состояние галочек со старта
        self.on_ri_toggled(self.ui.checkBox.isChecked())

    def on_ri_toggled(self, is_ri_known: bool):
        if not is_ri_known:
            # Если ПП неизвестен, пункты 4.2 и 4.3 строго True и блокируются для изменения
            self.ui.checkBox_2.setChecked(True)
            self.ui.checkBox_3.setChecked(True)
            self.ui.checkBox_2.setEnabled(False)
            self.ui.checkBox_3.setEnabled(False)
        else:
            # Если ПП известен, разблокируем пункты, давая пользователю выбор
            self.ui.checkBox_2.setEnabled(True)
            self.ui.checkBox_3.setEnabled(True)


class GalleryWidget(BaseProjectWidget):
    """Контроллер виджета галереи"""

    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_gallery()
        self.ui.setupUi(self)

        # 1. Настройка модели данных для QListView
        self.model = QStandardItemModel()
        self.ui.gallery_view.setModel(self.model)

        # Разрешаем множественный выбор через Shift и Ctrl
        self.ui.gallery_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Режим отображения иконок
        self.ui.gallery_view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.ui.gallery_view.setIconSize(QtCore.QSize(120, 120))
        self.ui.gallery_view.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.ui.gallery_view.setSpacing(10)

        # БЛОКИРОВКА ПЕРЕМЕЩЕНИЯ И РЕДАКТИРОВАНИЯ:
        self.ui.gallery_view.setMovement(QtWidgets.QListView.Movement.Static)
        self.ui.gallery_view.setDragEnabled(False)
        self.ui.gallery_view.setAcceptDrops(False)
        self.ui.gallery_view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        # Подключаем сортировку из UI (Qt Designer)
        self.ui.SortBycomboBox.currentIndexChanged.connect(self.sort_gallery)

        # 2. Инициализация дочерних окон
        self.data_info_dialog = DataInfoDialog(self)

        # 3. Подключение сигналов кнопок к слотам
        self.ui.load_imageButton.clicked.connect(self.load_images)
        self.ui.delete_imagesButton.clicked.connect(self.delete_images)
        self.ui.imgs_t_processButton.clicked.connect(self.images_to_process)
        self.ui.data_infoButton.clicked.connect(self.show_data_info)
        self.ui.roiButton.clicked.connect(self.show_roi)
        self.ui.boundButton.clicked.connect(self.show_boundaries)

    def load_images(self):
        """Загрузка изображений из проводника"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )

        if not file_paths:
            return

        for path in file_paths:
            filename = os.path.basename(path)
            pixmap = QPixmap(path)
            icon = QIcon(pixmap)

            item = QStandardItem(icon, filename)

            # Сохраняем полный путь (понадобится для процессинга)
            item.setData(path, QtCore.Qt.ItemDataRole.UserRole)

            # Сохраняем время изменения файла (File changed)
            file_mtime = os.path.getmtime(path)
            item.setData(file_mtime, QtCore.Qt.ItemDataRole.UserRole + 1)

            # Сохраняем время создания файла (File created, для Windows getctime = создание)
            file_ctime = os.path.getctime(path)
            item.setData(file_ctime, QtCore.Qt.ItemDataRole.UserRole + 2)

            flags = item.flags()
            flags &= ~QtCore.Qt.ItemFlag.ItemIsDragEnabled
            flags &= ~QtCore.Qt.ItemFlag.ItemIsEditable
            item.setFlags(flags)

            self.model.appendRow(item)

        # Применяем сортировку после загрузки новой партии
        self.sort_gallery()

    def sort_gallery(self):
        """Сортировка изображений согласно выбору в ComboBox"""
        if self.model.rowCount() == 0:
            return

        sort_type = self.ui.SortBycomboBox.currentText()
        items = []

        # Извлекаем все строки из модели
        while self.model.rowCount() > 0:
            items.append(self.model.takeRow(0))

        # Сортируем список строк в зависимости от выбранного критерия в Qt Designer
        if sort_type == "Name":
            items.sort(key=lambda row: row[0].text().lower())
        elif sort_type == "File changed":
            items.sort(key=lambda row: row[0].data(QtCore.Qt.ItemDataRole.UserRole + 1))
        elif sort_type == "File created":
            items.sort(key=lambda row: row[0].data(QtCore.Qt.ItemDataRole.UserRole + 2))

        # Возвращаем отсортированные строки обратно в модель
        for row in items:
            self.model.appendRow(row)

    def delete_images(self):
        """Удаление выбранных изображений из галереи"""
        selected_indexes = self.ui.gallery_view.selectionModel().selectedIndexes()

        if not selected_indexes:
            return

        # Удалять строки нужно строго с конца (reverse=True)
        for index in sorted(selected_indexes, key=lambda x: x.row(), reverse=True):
            self.model.removeRow(index.row())

    def images_to_process(self):
        """Подтверждение выбора изображений (пока заглушка)"""
        selected_indexes = self.ui.gallery_view.selectionModel().selectedIndexes()

        if not selected_indexes:
            QMessageBox.warning(self, "Warning", "Please select at least one image to process.")
            return

        selected_files = []
        for index in selected_indexes:
            file_path = self.model.data(index, QtCore.Qt.ItemDataRole.UserRole)
            selected_files.append(file_path)

        print(f"[{self.uid}] Ready to process {len(selected_files)} images:")
        for f in selected_files:
            print(f" -> {f}")

        # TODO: Здесь будет логика передачи путей дальше

    def show_data_info(self):
        """Открытие окна информации о датасете"""
        self.data_info_dialog.show()

    def show_roi(self):
        """Заглушка для окна ROI"""
        print(f"[{self.uid}] ROI window triggered.")

    def show_boundaries(self):
        """Заглушка для окна Boundaries"""
        print(f"[{self.uid}] Boundaries window triggered.")
import cv2
import numpy as np
from pathlib import Path
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon, QImage, QPixmap
from PyQt6.QtCore import Qt, QSize, QUuid

from program.gui.windows import Ui_Form_gallery
from .widgets_controller import WidgetsWindow
from ..small_controllers import UuidController


class GalleryWindow(WidgetsWindow):
    def __init__(self, link_name, link_idx, obj_type='gallery', state=None, linked=None, parent=None):
        super().__init__(link_name, link_idx, obj_type, state, linked, parent)
        self.setWindowFlag(Qt.WindowType.Window)

        self.ui = Ui_Form_gallery()
        self.ui.setupUi(self)
        self.setWindowTitle(link_name)

        self.images_model = QStandardItemModel(self)
        self.ui.gallery_view.setModel(self.images_model)

        self.ui.gallery_view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.ui.gallery_view.setIconSize(QSize(100, 100))
        self.ui.gallery_view.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.ui.gallery_view.setSpacing(10)
        self.ui.gallery_view.setWordWrap(True)

        self.ui.load_imageButton.clicked.connect(self.load_images)

        # Загружаем иконки из State при открытии проекта
        self._load_images_from_state()

    def load_images(self):
        """Загрузка новых файлов с диска с запоминанием последней папки."""
        if not self.state:
            return

        # 1. Получаем стартовую директорию из пользовательских настроек
        start_folder = str(self.state.user_settings.last_open_folder)

        # Открываем диалог, передавая стартовую директорию
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images",
            start_folder,
            "Images (*.tiff *.tif *.png *.jpg *.jpeg *.bmp)"
        )

        if not file_paths:
            return

        # 2. Сохраняем новую директорию в настройки
        selected_folder = Path(file_paths[0]).parent
        self.state.user_settings.last_open_folder = selected_folder
        self.state.user_settings.save()  # Физически записываем в paths.json

        datablock_uuid = self.linked

        for path_str in file_paths:
            path = Path(path_str)
            raw_uuid = QUuid.createUuid()
            img_uuid = UuidController.clean_uuid(raw_uuid)

            # Считываем картинку как numpy массив (сохраняя глубину цвета, например 16-бит)
            img_array = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img_array is None:
                print(f"[WARN] Не удалось прочитать файл: {path.name}")
                continue

            # Передаем массив в State (он пойдет на запись в Zarr)
            self.state.gallery.add_original_image(
                datablock_uuid=datablock_uuid,
                img_uuid=img_uuid,
                file_name=path.name,
                img_array=img_array
            )

            # Рисуем иконку
            item = QStandardItem(path.name)
            item.setIcon(QIcon(str(path)))
            item.setData(img_uuid, Qt.ItemDataRole.UserRole)
            self.images_model.appendRow(item)

    def _load_images_from_state(self):
        """Восстановление галереи: достаем массивы из датаблока и делаем из них иконки."""
        # 1. Принудительно очищаем UUID папки-родителя, чтобы 100% найти датаблок
        clean_linked = UuidController.clean_uuid(self.linked)

        print(f"\n[DEBUG GALLERY] Запуск восстановления изображений.")
        print(f"  -> Ищем датаблок по UUID: '{clean_linked}'")

        if not self.state or not clean_linked:
            print("  -> [WARN] State или Linked отсутствуют. Выход.")
            return

        saved_images = self.state.gallery.get_original_images(clean_linked)
        print(f"  -> Найдено изображений в State: {len(saved_images)}")

        for img_uuid, img_data in saved_images.items():

            # 🔥 УНИВЕРСАЛЬНАЯ РАСПАКОВКА ДАННЫХ
            if isinstance(img_data, dict):
                # Стандартный сценарий: словарь {name: ..., data: ...}
                file_name = img_data.get("name", f"Image_{img_uuid[:8]}")
                array_data = img_data.get("data")
            else:
                # Альтернативный сценарий: напрямую передан LazyBmipArray или массив
                array_data = img_data
                file_name = f"Image_{img_uuid[:8]}"  # Запасное имя на случай неудачи

                # Пытаемся вытащить оригинальное имя прямо из атрибутов Zarr-архива
                if hasattr(array_data, '_load_array'):
                    try:
                        z_arr = array_data._load_array()
                        # Безопасно извлекаем атрибуты в виде словаря
                        file_name = dict(z_arr.attrs).get("name", file_name)
                    except Exception as e:
                        print(f"  -> [WARN] Не удалось прочитать атрибуты Zarr для {img_uuid}: {e}")

            print(f"  -> Рендер иконки для: {file_name} (UUID: {img_uuid})")

            item = QStandardItem(file_name)

            # Превращаем сырой/ленивый массив в красивую иконку
            icon = self._create_icon_from_array(array_data)
            item.setIcon(icon)

            item.setData(img_uuid, Qt.ItemDataRole.UserRole)
            self.images_model.appendRow(item)

        print("[DEBUG GALLERY] Восстановление изображений завершено.\n")

    @staticmethod
    def _create_icon_from_array(array_data) -> QIcon:
        """Безопасно извлекает иконку из np.ndarray или LazyBmipArray."""
        if array_data is None:
            print("  -> [ERROR] array_data равен None!")
            return QIcon()

        try:
            # 1. Интеллектуальное чтение нужного среза
            if hasattr(array_data, 'shape'):
                # Если 3 измерения, но последний параметр не 3 и не 4 - это 3D-объем (Z, H, W)
                if len(array_data.shape) == 3 and array_data.shape[-1] not in [3, 4]:
                    mid_z = array_data.shape[0] // 2
                    img_np = array_data[mid_z]  # Берем центральный срез
                else:
                    img_np = array_data[:]  # Полная выгрузка из ленивого массива
            else:
                img_np = array_data

            print(f"  -> Массив успешно выгружен. Shape: {img_np.shape}, Dtype: {img_np.dtype}")

            # 2. Безопасная нормализация
            if img_np.dtype != np.uint8:
                img_np = cv2.normalize(img_np.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX)
                img_np = img_np.astype(np.uint8)

            # 3. Конвертация цветовых пространств
            if len(img_np.shape) == 2:
                img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
            elif len(img_np.shape) == 3:
                if img_np.shape[2] == 4:
                    img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
                elif img_np.shape[2] == 3:
                    # ОКТ картинки часто сохраняются как BGR из-за cv2.imread.
                    # Переводим в RGB, иначе цвета поедут в QImage.
                    img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)

            # 🔥 КРИТИЧЕСКИЙ ФИКС: Гарантируем непрерывность памяти для QImage
            img_np = np.ascontiguousarray(img_np)

            h, w, ch = img_np.shape
            bytes_per_line = ch * w

            # Делаем QImage и возвращаем QIcon
            q_img = QImage(img_np.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            if q_img.isNull():
                print("  -> [ERROR] QImage сгенерировал пустую картинку!")
                return QIcon()

            return QIcon(QPixmap.fromImage(q_img.copy()))

        except Exception as e:
            print(f"  -> [ERROR] Ошибка генерации иконки: {e}")
            import traceback
            traceback.print_exc()
            return QIcon()
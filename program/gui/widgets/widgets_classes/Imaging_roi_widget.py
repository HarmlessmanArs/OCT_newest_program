import cv2
import numpy as np
from PyQt6 import QtCore, QtWidgets, QtGui

from ..base_widget import BaseProjectWidget
from ...windows.ui_imaging_roi_window import Ui_Form_img_roi


# Импортируем твою математику (путь подстрой под свою структуру)
# from ...math.boundaries_extraction import process_single_image 


class InteractiveRoiScene(QtWidgets.QGraphicsScene):
    """Кастомная сцена для обработки мыши и интерактивного рисования ROI"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_item = None
        self.roi_rect_item = None
        self.start_point = None

    def set_image(self, pixmap: QtGui.QPixmap):
        """Очищает сцену и устанавливает новое изображение"""
        self.clear()
        self.image_item = self.addPixmap(pixmap)

        # Создаем пустой прямоугольник для ROI (Красный цвет, толщина 2, пунктир)
        self.roi_rect_item = QtWidgets.QGraphicsRectItem()
        self.roi_rect_item.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.red, 2, QtCore.Qt.PenStyle.DashLine))
        self.addItem(self.roi_rect_item)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        """Начало рисования рамки"""
        if self.image_item and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.start_point = event.scenePos()
            self.roi_rect_item.setRect(QtCore.QRectF(self.start_point, self.start_point))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        """Изменение размера рамки при движении мыши"""
        if self.start_point and (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
            current_point = event.scenePos()

            # Нормализуем прямоугольник (чтобы можно было тянуть рамку в любую сторону)
            rect = QtCore.QRectF(self.start_point, current_point).normalized()

            # Строго ограничиваем ROI пределами картинки
            if self.image_item:
                img_rect = self.image_item.boundingRect()
                rect = rect.intersected(img_rect)

            self.roi_rect_item.setRect(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        """Фиксация рамки"""
        self.start_point = None
        super().mouseReleaseEvent(event)

    def get_roi_coordinates(self):
        """Возвращает координаты ROI в формате [x1, x2, y1, y2]"""
        if not self.roi_rect_item:
            return [0, 0, 0, 0]

        rect = self.roi_rect_item.rect()
        return [int(rect.left()), int(rect.right()), int(rect.top()), int(rect.bottom())]


class RoiWidget(BaseProjectWidget):
    """Контроллер виджета ROI"""

    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_img_roi()
        self.ui.setupUi(self)

        # 1. Привязываем нашу кастомную сцену к QGraphicsView из Qt Designer
        self.scene = InteractiveRoiScene(self)
        self.ui.image_graphView.setScene(self.scene)

        # Улучшаем качество рендера
        self.ui.image_graphView.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self.ui.image_graphView.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing |
            QtGui.QPainter.RenderHint.SmoothPixmapTransform
        )

        # 2. Подключение кнопок
        self.ui.processButton.clicked.connect(self.process_roi)

        # Локальное хранилище данных
        self.combined_img_gray = None

    def setup_combined_image(self, file_paths: list):
        """
        Загружает список изображений, усредняет их и выводит на экран.
        """
        if not file_paths:
            return

        images = []
        for path in file_paths:
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                images.append(img)

        if not images:
            QtWidgets.QMessageBox.warning(self, "Error", "Could not read the selected images.")
            return

        # Находим усредненное изображение по пикселям 
        stacked = np.stack(images, axis=0)
        self.combined_img_gray = np.mean(stacked, axis=0).astype(np.uint8)

        # Конвертируем numpy array в QPixmap
        h, w = self.combined_img_gray.shape
        qimg = QtGui.QImage(self.combined_img_gray.data, w, h, w, QtGui.QImage.Format.Format_Grayscale8)
        pixmap = QtGui.QPixmap.fromImage(qimg)

        # Отправляем на сцену и подгоняем масштаб окна
        self.scene.set_image(pixmap)
        self.ui.image_graphView.fitInView(self.scene.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def process_roi(self):
        """Сбор данных из UI и запуск математики поиска границ"""
        if self.combined_img_gray is None:
            QtWidgets.QMessageBox.warning(self, "Warning", "No combined image generated. Select images first.")
            return

        roi_coords = self.scene.get_roi_coordinates()

        # Защита от нулевого ROI
        if roi_coords == [0, 0, 0, 0] or (roi_coords[0] == roi_coords[1]) or (roi_coords[2] == roi_coords[3]):
            QtWidgets.QMessageBox.warning(self, "Warning", "Please draw a valid ROI on the image.")
            return

        # Считываем параметры из SpinBox'ов интерфейса
        bounds_amount = self.ui.boundaries_amountSpinBox.value()
        shift_val = self.ui.shift_amountSpinBox.value()

        print(f"[{self.uid}] Processing ROI: {roi_coords} | Bounds: {bounds_amount} | Shift: {shift_val}")

        # --- ВЫЗОВ МАТЕМАТИКИ ИЗ BOUNDARIES_EXTRACTION.PY ---
        # Раскомментируй этот блок, когда наладишь импорт process_single_image
        """
        result_img_bgr = process_single_image(
            img_gray=self.combined_img_gray, 
            graph_coordinates=roi_coords, 
            amount_of_bounds=bounds_amount, 
            shift=shift_val
        )

        if result_img_bgr is not None:
            # Конвертируем результат (BGR из OpenCV) в RGB для Qt
            result_img_rgb = cv2.cvtColor(result_img_bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = result_img_rgb.shape
            bytes_per_line = ch * w
            qimg = QtGui.QImage(result_img_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)

            # Показываем финальный результат с отрисованными границами
            self.scene.set_image(QtGui.QPixmap.fromImage(qimg))
            self.ui.image_graphView.fitInView(self.scene.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        """
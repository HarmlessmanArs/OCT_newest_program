from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QMenu, QMdiArea, QMdiSubWindow
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt
from program.gui.windows import Ui_Form_gallery
from .widgets_controller import WidgetsWindow


class GalleryWindow(WidgetsWindow):

    def __init__(self, link_name, link_idx, obj_type='gallery', linked=None, parent=None):
        super().__init__(link_name, link_idx, obj_type, linked, parent)
        self.setWindowFlag(Qt.WindowType.Window)

        self.ui = Ui_Form_gallery()
        self.ui.setupUi(self)

        self.setWindowTitle(link_name)
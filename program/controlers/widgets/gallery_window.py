from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QMenu, QMdiArea, QMdiSubWindow
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt
from program.gui.windows import Ui_Form_gallery
from .widgets import WidgetsWindow


class GalleryWindow(WidgetsWindow):

    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self.setWindowFlag(Qt.WindowType.Window)

        self.ui = Ui_Form_gallery()
        self.ui.setupUi(self)

        self.setWindowTitle(name)
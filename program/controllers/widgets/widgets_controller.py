from PyQt6 import QtWidgets, QtGui, QtCore
from ...utils import LinkBase
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QMenu, QMdiArea, QMdiSubWindow
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt

class WidgetsWindow(LinkBase, QtWidgets.QWidget):
    # Сигнал для уведомления MainWindow о закрытии окна
    window_closed = QtCore.pyqtSignal(object)

    def __init__(self, link_name, link_idx, obj_type, linked=None, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        LinkBase.__init__(self, link_name, link_idx, obj_type, linked)

    def rename(self, new_name: str):
        self.link_name = new_name
        self.setWindowTitle(new_name)

    def closeEvent(self, event: QtGui.QCloseEvent):
        reply = QtWidgets.QMessageBox.question(
            self, "Confirmation",
            f"Close window {self.obj_type} named {self.link_name}?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No |
            QtWidgets.QMessageBox.StandardButton.Ignore
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.window_closed.emit(self)
            event.accept()
        elif reply == QtWidgets.QMessageBox.StandardButton.Ignore:
            # "Игнорировать" в данном контексте используем как "Свернуть"
            event.ignore()
            if self.parent() and isinstance(self.parent(), QtWidgets.QMdiSubWindow):
                self.parent().showMinimized()
        else:
            event.ignore()

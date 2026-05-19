from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QMenu, QMdiArea, QMdiSubWindow
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt

class WidgetsWindow(QtWidgets.QWidget):
    # Сигнал для уведомления MainWindow о закрытии окна
    window_closed = QtCore.pyqtSignal(object)

    def __init__(self, name: str, parent=None, idx: int | str = None):
        super().__init__(parent)
        self.id = idx
        self.name = name
        self.setWindowTitle(name)
        self.force_close = False

    def rename(self, new_name: str):
        self.name = new_name
        self.setWindowTitle(new_name)

    def closeEvent(self, event: QtGui.QCloseEvent):
        if self.force_close:
            event.accept()
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Подтверждение",
            f"Закрыть окно '{self.name}'?",
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

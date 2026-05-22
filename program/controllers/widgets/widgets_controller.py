from PyQt6 import QtWidgets, QtGui, QtCore
from ...utils import LinkBase


class WidgetsWindow(LinkBase, QtWidgets.QWidget):
    # Сигнал для уведомления MainWindow о закрытии окна
    window_closed = QtCore.pyqtSignal(object)

    def __init__(self, link_name, link_idx, obj_type, linked=None, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        LinkBase.__init__(self, link_name, link_idx, obj_type, linked)

        # НАСТРОЙКА: Флаг принудительного закрытия (без вызова QMessageBox)
        self._force_close = False

    def rename(self, new_name: str):
        self.link_name = new_name
        self.setWindowTitle(new_name)

    def closeEvent(self, event: QtGui.QCloseEvent):
        # Если удаление вызвано со стороны дерева — закрываем без лишних вопросов
        if self._force_close:
            event.accept()
            return

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
            event.ignore()
            if self.parent() and isinstance(self.parent(), QtWidgets.QMdiSubWindow):
                self.parent().showMinimized()
        else:
            event.ignore()
from ...libraries import *

class WidgetsWindow(QtWidgets.QWidget):

    def __init__(self, name, parent=None):
        super().__init__(parent)

        self.name = name
        self.setWindowTitle(name)

    def rename(self, new_name):
        self.name = new_name
        self.setWindowTitle(new_name)

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Перехват закрытия окна"""

        # Создаем диалоговое окно
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("Close window?")
        msg_box.setText(f"What do you want to do with '{self.name}'?")

        # Добавляем кастомные кнопки
        close_btn = msg_box.addButton("Close", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        minimize_btn = msg_box.addButton("Minimize", QtWidgets.QMessageBox.ButtonRole.ActionRole)
        cancel_btn = msg_box.addButton("Cancel", QtWidgets.QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()  # Запускаем диалог

        clicked_button = msg_box.clickedButton()

        if clicked_button == close_btn:
            # Разрешаем закрытие
            event.accept()

        elif clicked_button == minimize_btn:
            # Игнорируем закрытие и сворачиваем
            event.ignore()
            # Если виджет в MDI, нужно сворачивать именно subwindow
            if self.parent() and isinstance(self.parent(), QtWidgets.QMdiSubWindow):
                self.parent().showMinimized()
            else:
                self.showMinimized()
        else:
            # Нажата отмена или крестик диалога — ничего не делаем
            event.ignore()
import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
# Импорт вашего главного окна
from ..controllers.windows.main_window_controller import MainWindow


def exception_hook(exc_type, exc_value, exc_tb):
    """
    Перехватывает ошибки Python, чтобы PyQt6 не схлопывался с кодом 0xC0000409.
    Выводит ошибку в консоль и показывает всплывающее окно с traceback.
    """
    # 1. Печатаем в консоль (stderr)
    print("CRITICAL ERROR CATCHED:", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_tb)

    # 2. Формируем текст для окна с ошибкой
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    # 3. Показываем визуальное уведомление
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setWindowTitle("Критическая ошибка Python")
    msg_box.setText(f"Произошла необработанная ошибка:\n{exc_type.__name__}: {exc_value}")
    msg_box.setDetailedText(error_msg)

    # Делаем окно достаточно широким для удобного чтения лога
    msg_box.setStyleSheet("QTextEdit { min-width: 600px; min-height: 400px; }")
    msg_box.exec()


# ПЕРЕХВАТЧИК СТАВИТСЯ ЗДЕСЬ — на уровне модуля, до запуска функции gui_main
sys.excepthook = exception_hook


def gui_main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
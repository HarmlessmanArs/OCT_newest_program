import sys
import traceback
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal


class _ExceptionSignaler(QObject):
    """
    Вспомогательный класс для потокобезопасной передачи ошибки.
    Гарантирует, что окно ошибки всегда будет вызвано в главном потоке UI.
    """
    error_caught = pyqtSignal(str, str)


class ErrorManager:
    """
    Глобальный перехватчик исключений (Crash Manager).
    Записывает краши в файл и выводит понятное окно пользователю.
    """

    def __init__(self, log_dir: str | Path = "logs"):
        # 1. Настройка папки для логов
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "crash_log.txt"

        # 2. Настройка базового логирования Python
        logging.basicConfig(
            filename=str(self.log_file),
            level=logging.ERROR,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )

        # 3. Подключение сигнала к функции отрисовки интерфейса
        self.signaler = _ExceptionSignaler()
        self.signaler.error_caught.connect(self._show_error_dialog)

    def setup_hooks(self):
        """Активирует перехват всех глобальных ошибок Python"""
        sys.excepthook = self._global_exception_handler

    def _global_exception_handler(self, exc_type, exc_value, exc_traceback):
        """
        Метод вызывается автоматически при любом критическом падении программы,
        которое не было обернуто в try...except.
        """
        # Пропускаем стандартное прерывание с клавиатуры (Ctrl+C в консоли)
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # Формируем полный текст ошибки (Traceback)
        traceback_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        # 1. Записываем в лог-файл
        logging.error(f"КРИТИЧЕСКАЯ ОШИБКА:\n{traceback_text}")

        # 2. Формируем короткое сообщение для окна
        short_msg = f"{exc_type.__name__}: {str(exc_value)}"

        # 3. Отправляем сигнал в UI-поток для показа окна
        self.signaler.error_caught.emit(short_msg, traceback_text)

    def _show_error_dialog(self, short_msg: str, full_traceback: str):
        """Отображает окно с ошибкой (строго в главном потоке)"""
        app = QApplication.instance()
        if app:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Критическая ошибка ОКТ программы")
            msg_box.setText(
                "Произошла непредвиденная ошибка. Рекомендуется сохранить проект и перезапустить программу.")
            msg_box.setInformativeText(f"Описание:\n{short_msg}\n\nПолный отчет сохранен в папку logs.")

            # Кнопка "Show Details..." покажет полный Traceback прямо в программе
            msg_box.setDetailedText(full_traceback)
            msg_box.exec()
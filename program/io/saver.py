# program/io/saver.py
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from program.core.state import ProjectState
from program.io.project_manager import ProjectManager


class SaveProjectWorker(QThread):
    """
    Поток для фонового сохранения проекта без зависания GUI PyQt6.
    Использует новую архитектуру через ProjectManager.
    """
    work_finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int)

    def __init__(self, state: ProjectState, target_path: str | Path, manager: ProjectManager):
        super().__init__()
        self.state = state
        self.target_path = target_path
        self.manager = manager

    def run(self):
        try:
            self.progress.emit(10)

            # Вся сложная логика Ввода/Вывода теперь умещается в одну строчку!
            self.manager.save_project(self.state, self.target_path)

            self.progress.emit(100)
            self.work_finished.emit(True, "")
        except Exception as e:
            # Если возникнет ошибка доступа (WinError) или другая проблема,
            # программа не вылетит, а покажет красивое окно с ошибкой.
            self.work_finished.emit(False, f"Ошибка сохранения: {str(e)}")
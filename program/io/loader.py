# program/io/loader.py
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from program.core.state import ProjectState
from program.io.project_manager import ProjectManager


class LoadProjectWorker(QThread):
    """
    Поток для фоновой загрузки проекта без зависания GUI.
    """
    work_finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int)

    def __init__(self, state: ProjectState, source_path: str | Path, manager: ProjectManager):
        super().__init__()
        self.state = state
        self.source_path = source_path
        self.manager = manager

    def run(self):
        try:
            self.progress.emit(10)

            # Менеджер сам распакует архив, обновит стейт и подгрузит TIFF-файлы лениво
            self.manager.load_project(self.state, self.source_path)

            self.progress.emit(100)
            self.work_finished.emit(True, "")
        except Exception as e:
            self.work_finished.emit(False, f"Ошибка загрузки: {str(e)}")
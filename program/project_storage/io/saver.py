from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from .writer import ProjectWriter

class SaveProjectWorker(QThread):
    """Поток для фонового сохранения проекта без зависания GUI PyQt6"""
    finished = pyqtSignal(bool, str)  # (Успех: bool, Сообщение: str)
    progress = pyqtSignal(int)        # Прогресс записи (0-100%)

    def __init__(self, target_path: str | Path, project_snapshot: dict):
        super().__init__()
        self.target_path = Path(target_path)
        self.snapshot = project_snapshot

    def run(self):
        writer = ProjectWriter(self.target_path)
        try:
            writer.write(self.snapshot, progress_callback=self.progress.emit)
            self.finished.emit(True, "Проект успешно сохранен!")
        except Exception as e:
            self.finished.emit(False, str(e))
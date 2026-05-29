import copy
from pathlib import Path
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QUuid
from .writer import ProjectWriter


def sanitize_snapshot(obj):
    if isinstance(obj, dict):
        return {str(k): sanitize_snapshot(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_snapshot(item) for item in obj]
    elif isinstance(obj, QUuid):
        return obj.toString()
    elif isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


class SaveProjectWorker(QThread):
    """Поток для фонового сохранения проекта без зависания GUI PyQt6"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int)

    def __init__(self, target_path: str | Path, project_snapshot: dict):
        super().__init__()
        self.target_path = Path(target_path)
        self.snapshot = project_snapshot

    def run(self):
        try:
            print("\n" + "=" * 60)
            print("[DEBUG SAVER] >>> НАЧАЛО СОХРАНЕНИЯ ПРОЕКТА <<<")
            print(f"[DEBUG SAVER] Целевой файл: {self.target_path}")
            print(f"[DEBUG SAVER] Исходные ключи снапшота: {list(self.snapshot.keys())}")

            # Телеметрия содержимого до очистки
            if 'hierarchy' in self.snapshot:
                print(f"[DEBUG SAVER] Найдено папок в 'hierarchy': {len(self.snapshot['hierarchy'])}")
            if 'widgets' in self.snapshot:
                print(f"[DEBUG SAVER] Найдено виджетов в 'widgets': {len(self.snapshot['widgets'])}")
            if 'tree_structure' in self.snapshot:
                print(f"[DEBUG SAVER] Присутствует старая 'tree_structure'")

            # 1. Очистка данных
            print("[DEBUG SAVER] Запуск очистки типов (sanitize_snapshot)...")
            clean_snapshot = sanitize_snapshot(self.snapshot)
            print(f"[DEBUG SAVER] Ключи снапшота ПОСЛЕ очистки: {list(clean_snapshot.keys())}")

            # 2. Удаление старого файла
            if self.target_path.exists():
                print("[DEBUG SAVER] Обнаружен старый файл. Удаляем для перезаписи...")
                self.target_path.unlink(missing_ok=True)

            # 3. Передача писателю
            print("[DEBUG SAVER] Передача данных в ProjectWriter...")
            writer = ProjectWriter(self.target_path)
            writer.write(clean_snapshot, progress_callback=self.progress.emit)

            print("[DEBUG SAVER] <<< СОХРАНЕНИЕ УСПЕШНО ЗАВЕРШЕНО >>>")
            print("=" * 60 + "\n")
            self.finished.emit(True, "Project saved completely!")

        except Exception as e:
            print(f"[DEBUG SAVER] ❌ КРИТИЧЕСКАЯ ОШИБКА В ПОТОКЕ: {str(e)}")
            import traceback
            traceback.print_exc()
            print("=" * 60 + "\n")
            self.finished.emit(False, str(e))
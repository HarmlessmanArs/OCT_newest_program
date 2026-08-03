# state/temp_manager.py

import tempfile
import shutil
import atexit
from pathlib import Path


class TempWorkspace:
    def __init__(self, custom_base_dir: Path | None = None):
        """
        Если custom_base_dir указан и существует, кэш создается там (например, D:/OCT_Cache).
        Иначе используется системный Temp ОС.
        """
        self._custom_base_dir = custom_base_dir
        self._create_temp_directory()
        atexit.register(self.cleanup)

    def _create_temp_directory(self):
        """Внутренний метод для безопасного создания папки."""
        if self._custom_base_dir and self._custom_base_dir.exists():
            # Создаем в месте, указанном пользователем
            self._temp_dir = Path(tempfile.mkdtemp(prefix="oct_project_", dir=self._custom_base_dir))
        else:
            # Создаем в системном Temp
            self._temp_dir = Path(tempfile.mkdtemp(prefix="oct_project_"))

        print(f"[TempWorkspace] Создана временная директория: {self._temp_dir}")

    # ... (root и get_block_dir остаются без изменений) ...

    def reset(self):
        self.cleanup()
        self._create_temp_directory()  # Используем переписанный метод

    def cleanup(self):
        if hasattr(self, '_temp_dir') and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir)
                print(f"[TempWorkspace] Директория {self._temp_dir} успешно очищена.")
            except OSError as e:
                print(f"[TempWorkspace] Ошибка очистки директории: {e}")
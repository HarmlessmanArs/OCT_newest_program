# state/user_settings_state.py

from dataclasses import dataclass
from pathlib import Path
import json


def _config_dir() -> Path:
    # Используем скрытую папку с точкой в начале
    base = Path.home() / ".OCT_program"
    base.mkdir(parents=True, exist_ok=True)
    return base


SETTINGS_FILE = _config_dir() / "settings.json"

@dataclass
class UserSettingsState:
    last_open_folder: Path = Path.home()
    last_save_project_folder: Path = Path.home()
    last_processing_folder: Path = Path.home()
    last_save_folder_for_files: Path = Path.home()
    last_save_folder_for_images: Path = Path.home()
    # НОВОЕ ПОЛЕ: Кастомная папка для кэша (Scratch Disk)
    workspace_temp_folder: Path | None = None

    @classmethod
    def load(cls) -> "UserSettingsState":
        if not SETTINGS_FILE.exists():
            return cls()

        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))

            def get_valid_path(key: str) -> Path:
                # ... (твой существующий код) ...
                path_str = data.get(key)
                if path_str:
                    path = Path(path_str)
                    if path.exists():
                        return path
                return Path.home()

            # Функция для безопасного чтения кастомного Temp
            def get_temp_path(key: str) -> Path | None:
                path_str = data.get(key)
                if path_str:
                    path = Path(path_str)
                    if path.exists():
                        return path
                return None

            return cls(
                last_open_folder=get_valid_path("last_open_folder"),
                last_save_project_folder=get_valid_path("last_save_project_folder"),
                last_processing_folder=get_valid_path("last_processing_folder"),
                last_save_folder_for_files=get_valid_path("last_save_folder_for_files"),
                last_save_folder_for_images=get_valid_path("last_save_folder_for_images"),
                workspace_temp_folder=get_temp_path("workspace_temp_folder")  # Загружаем
            )
        except (json.JSONDecodeError, OSError):
            return cls()

    def save(self) -> None:
        try:
            SETTINGS_FILE.write_text(
                json.dumps(
                    {
                        "last_open_folder": str(self.last_open_folder),
                        "last_save_project_folder": str(self.last_save_project_folder),
                        "last_processing_folder": str(self.last_processing_folder),
                        "last_save_folder_for_files": str(self.last_save_folder_for_files),
                        "last_save_folder_for_images": str(self.last_save_folder_for_images),
                        # Сохраняем строку или null (None)
                        "workspace_temp_folder": str(self.workspace_temp_folder) if self.workspace_temp_folder else None
                    },
                    indent=4,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )
        except OSError as e:
            print(f"[Настройки] Ошибка сохранения: {e}")
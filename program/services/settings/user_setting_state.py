# user_settings_state.py

from dataclasses import dataclass
from pathlib import Path
import json


def _config_dir() -> Path:
    base = Path.home() / "OCT_program"
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

    @classmethod
    def load(cls) -> "UserSettingsState":
        if not SETTINGS_FILE.exists():
            return cls()

        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return cls(
            last_open_folder=Path(data.get("last_open_folder", Path.home())),
            last_save_project_folder=Path(data.get("last_save_project_folder", Path.home())),
            last_processing_folder=Path(data.get("last_processing_folder", Path.home())),
            last_save_folder_for_files=Path(data.get("last_save_folder_for_files", Path.home())),
            last_save_folder_for_images=Path(data.get("last_save_folder_for_images", Path.home()))
        )

    def save(self) -> None:
        SETTINGS_FILE.write_text(
            json.dumps(
                {
                    "last_open_folder": str(self.last_open_folder),
                    "last_save_project_folder": str(self.last_save_project_folder),
                    "last_processing_folder": str(self.last_processing_folder),
                    "last_save_folder_for_files": str(self.last_save_folder_for_files),
                    "last_save_folder_for_images": str(self.last_save_folder_for_images),
                },
                indent=4,
            ),
            encoding="utf-8",
        )

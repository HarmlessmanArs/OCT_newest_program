import os
import zipfile
import shutil
from pathlib import Path
import numpy as np

# Подставляй свои реальные импорты:
from ..core.state import ProjectState
from ..state.temp_manager import TempWorkspace
from .serializer import ProjectSerializer
from .tiff_handler import TiffHandler


class ProjectManager:
    """
    Главный фасад для Ввода/Вывода. Управляет сохранением и ленивой загрузкой
    проектов .bmip через промежуточную буферную зону.
    """

    def __init__(self, temp_workspace: TempWorkspace):
        self.temp_workspace = temp_workspace

    def _get_temp_dir(self) -> Path:
        """Безопасное получение пути к временной папке буфера"""
        if hasattr(self.temp_workspace, 'root'):
            return Path(self.temp_workspace.root)
        elif hasattr(self.temp_workspace, 'get_path'):
            return Path(self.temp_workspace.get_path())
        elif hasattr(self.temp_workspace, '_temp_dir'):
            return Path(self.temp_workspace._temp_dir)
        else:
            raise AttributeError("TempWorkspace не содержит доступного пути к временной папке")

    def save_project(self, state: ProjectState, target_filepath: Path | str) -> None:
        """Сохраняет текущее состояние проекта в .bmip архив."""
        target_filepath = Path(target_filepath)

        # Берем актуальную папку. Никаких reset() здесь не делаем!
        temp_dir = self._get_temp_dir()

        # УМНАЯ ОЧИСТКА: удаляем только файлы узлов, которых больше нет в ProjectState
        nodes_dir = temp_dir / "nodes"
        if nodes_dir.exists():
            for node_folder in nodes_dir.iterdir():
                if node_folder.is_dir() and node_folder.name not in state.nodes:
                    shutil.rmtree(node_folder, ignore_errors=True)

        # Шаг 2: Сериализуем метаданные и структуру
        metadata_json = ProjectSerializer.serialize_state(state)
        metadata_path = temp_dir / "metadata.json"
        metadata_path.write_text(metadata_json, encoding='utf-8')

        # Шаг 3: Сохраняем тяжелые матрицы (если они есть)
        nodes_dir.mkdir(exist_ok=True)
        for uid, node in state.nodes.items():
            if isinstance(node.data, np.ndarray):
                node_folder = nodes_dir / uid
                node_folder.mkdir(exist_ok=True)

                tiff_path = node_folder / "data.tiff"
                TiffHandler.save_array(tiff_path, node.data, compress=False)

        # Шаг 4: Упаковываем всё в .bmip (без сжатия, с атомарной подменой)
        self._pack_to_bmip(temp_dir, target_filepath)

        # Обновляем состояние
        state.filepath = str(target_filepath)
        state.is_modified = False

    def load_project(self, state: ProjectState, source_filepath: Path | str) -> None:
        """Загружает проект из .bmip архива (с ленивой подгрузкой изображений)."""
        source_filepath = Path(source_filepath)
        if not source_filepath.exists():
            raise FileNotFoundError(f"Файл не найден: {source_filepath}")

        # Шаг 1: Полный сброс буфера (удалит старую папку и создаст новую)
        self.temp_workspace.reset()

        # Шаг 2: ВАЖНО! Получаем путь ТОЛЬКО ПОСЛЕ сброса!
        temp_dir = self._get_temp_dir()

        # Распаковываем архив
        self._unpack_from_bmip(source_filepath, temp_dir)

        # Шаг 3: Восстанавливаем базовую структуру из JSON
        metadata_path = temp_dir / "metadata.json"
        if not metadata_path.exists():
            raise ValueError("Поврежденный файл проекта: отсутствует metadata.json")

        json_str = metadata_path.read_text(encoding='utf-8')
        ProjectSerializer.deserialize_to_state(json_str, state)

        # Шаг 4: Лениво привязываем матрицы (Memory Mapping)
        nodes_dir = temp_dir / "nodes"
        if nodes_dir.exists():
            for uid, node in state.nodes.items():
                tiff_path = nodes_dir / uid / "data.tiff"
                if tiff_path.exists():
                    node.data = TiffHandler.load_array(tiff_path, use_memmap=True)

        # Обновляем состояние
        state.filepath = str(source_filepath)
        state.is_modified = False

    def _pack_to_bmip(self, source_dir: Path, target_bmip_path: Path) -> None:
        """Сборка папки в архив без сжатия."""
        tmp_target = target_bmip_path.with_suffix('.bmip.tmp')

        with zipfile.ZipFile(tmp_target, 'w', compression=zipfile.ZIP_STORED) as zf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zf.write(file_path, arcname)

        os.replace(tmp_target, target_bmip_path)

    def _unpack_from_bmip(self, source_bmip_path: Path, target_dir: Path) -> None:
        """Распаковка архива в папку."""
        with zipfile.ZipFile(source_bmip_path, 'r') as zf:
            zf.extractall(target_dir)
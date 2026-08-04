import numpy as np
import tifffile
from pathlib import Path
from typing import Union


class TiffHandler:
    """
    Утилита для безопасного сохранения и чтения ОКТ-данных в формате TIFF.
    Гарантирует сохранение 32-bit float массивов без потерь и нормализации.
    """

    @staticmethod
    def save_array(file_path: Union[str, Path], array: np.ndarray, compress: bool = False) -> None:
        """
        Сохраняет NumPy массив в TIFF файл внутри временной зоны (TempWorkspace).

        :param file_path: Путь к итоговому .tiff файлу.
        :param array: NumPy массив (2D или 3D).
        :param compress: Использовать ли zlib сжатие. По умолчанию False, чтобы
                         сохранение по Ctrl+S происходило мгновенно и не грузило CPU.
        """
        file_path = Path(file_path)

        # Убедимся, что целевая папка (например, original_images) существует
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Настройка сжатия
        compression = 'zlib' if compress else None

        # Сохраняем массив. photometric='minisblack' говорит просмотрщикам,
        # что 0 - это черный цвет (стандарт для ОКТ).
        tifffile.imwrite(
            file_path,
            array,
            compression=compression,
            photometric='minisblack'
        )

    @staticmethod
    def load_array(file_path: Union[str, Path], use_memmap: bool = True) -> np.ndarray:
        """
        Загружает TIFF файл в NumPy массив.

        :param file_path: Путь к .tiff файлу.
        :param use_memmap: Если True, использует ленивую загрузку (Memory Mapping).
                           Файл не грузится в RAM целиком, а читается с диска
                           только в момент обращения к конкретным пикселям.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Файл TIFF не найден: {file_path}")

        if use_memmap:
            # Идеально для тяжелых ОКТ-томограмм (экономит гигабайты оперативки)
            return tifffile.memmap(file_path)
        else:
            # Полная загрузка в оперативную память
            return tifffile.imread(file_path)
import zarr
from zarr.storage import ZipStore
import numpy as np
from pathlib import Path

class LazyBmipArray:
    """
    Прокси-класс для работы с тяжелыми массивами в ОКТ-программе без забивания RAM.
    Открывает файл только на момент чтения, гарантируя отсутствие блокировок ОС (WinError 5).
    """

    def __init__(self, file_path: str | Path, dataset_path: str):
        self.file_path = str(file_path)
        self.dataset_path = dataset_path

    def _read_array_attr(self, attr_name):
        """Безопасно открывает архив, читает атрибут массива и сразу закрывает файл."""
        store = ZipStore(self.file_path, mode='r')
        try:
            arr = zarr.open_array(store=store, path=self.dataset_path, mode='r')
            return getattr(arr, attr_name)
        finally:
            store.close()

    def _read_data(self, item=None):
        """Безопасно открывает архив, считывает кусок данных и сразу закрывает файл."""
        store = ZipStore(self.file_path, mode='r')
        try:
            arr = zarr.open_array(store=store, path=self.dataset_path, mode='r')
            if item is None:
                return arr[:]
            return arr[item]
        finally:
            store.close()

    @property
    def shape(self):
        return self._read_array_attr('shape')

    @property
    def ndim(self):
        return self._read_array_attr('ndim')

    @property
    def dtype(self):
        return self._read_array_attr('dtype')

    def __getitem__(self, item):
        return self._read_data(item)

    def load_fully(self) -> np.ndarray:
        """Принудительно загружает весь массив в память как стандартный numpy.ndarray"""
        return self._read_data()
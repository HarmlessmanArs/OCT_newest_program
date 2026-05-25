import zarr
import numpy as np


class LazyBmipArray:
    """Прокси-класс для работы с тяжелыми массивами в ОКТ-программе без забивания RAM"""

    def __init__(self, store, dataset_path: str):
        self.store = store
        self.dataset_path = dataset_path
        self._array = None

    def _load_array(self):
        if self._array is None:
            # Безопасное открытие конкретного массива по его внутреннему пути под Zarr 3.x
            self._array = zarr.open_array(store=self.store, path=self.dataset_path, mode='r')
        return self._array

    @property
    def shape(self):
        return self._load_array().shape

    @property
    def ndim(self):
        return self._load_array().ndim

    @property
    def dtype(self):
        return self._load_array().dtype

    def __getitem__(self, item):
        """
        Позволяет делать срезы [0, :, :] или [:] напрямую из ZIP без полной выгрузки в RAM.
        Применяется виджетами визуализации (галереи, графики, маппинг).
        """
        return self._load_array()[item]

    def load_fully(self) -> np.ndarray:
        """Принудительно загружает весь массив в память как стандартный numpy.ndarray"""
        return self._load_array()[:]
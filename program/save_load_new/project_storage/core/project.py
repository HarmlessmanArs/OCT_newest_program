from typing import List
from .dataset import Dataset


class Project:
    def __init__(self, version: int = 2):
        self.version = version
        self.datasets: List[Dataset] = []
        self.global_data: dict = {}

    def add_dataset(self, dataset: Dataset):
        self.datasets.append(dataset)
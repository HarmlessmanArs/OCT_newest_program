from typing import Dict
from .datablock import DataBlock


class Dataset:
    def __init__(self, dataset_id: str, name: str):
        self.id = dataset_id
        self.name = name
        self.blocks: Dict[str, DataBlock] = {}
        self.metadata: dict = {}

    def add_block(self, block: DataBlock):
        self.blocks[block.name] = block

    def get_block(self, name: str):
        return self.blocks.get(name)
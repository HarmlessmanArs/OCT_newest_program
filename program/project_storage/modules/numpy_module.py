import numpy as np
from .base import SaveModule, LoadModule


class NumpySaveModule(SaveModule):

    def can_handle(self, block):
        return block.type == "ndarray"

    def save(self, block, writer):
        path = block.handle.path
        writer.write_npy(path, block.meta["array"])


class NumpyLoadModule(LoadModule):

    def can_handle(self, handle):
        return handle.loader_type == "npy"

    def load(self, handle, reader):
        return reader.read_npy(handle.path)
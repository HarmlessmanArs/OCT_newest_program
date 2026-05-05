import json
from .base import SaveModule, LoadModule


class JsonSaveModule(SaveModule):

    def can_handle(self, block):
        return block.type == "json"

    def save(self, block, writer):
        writer.write_json(block.handle.path, block.meta["data"])


class JsonLoadModule(LoadModule):

    def can_handle(self, handle):
        return handle.loader_type == "json"

    def load(self, handle, reader):
        return reader.read_json(handle.path)
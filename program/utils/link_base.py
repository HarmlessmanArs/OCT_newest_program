from PyQt6 import QtCore


class LinkBase:
    def __init__(self, link_name: str, link_idx: str | QtCore.QUuid, obj_type: str, linked: str | None):
        self.link_name = link_name
        self.link_idx = link_idx
        self.obj_type = obj_type
        self.linked = linked
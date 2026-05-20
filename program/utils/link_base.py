class LinkBase:
    def __init__(self, idx: int, name: str, obj_type: str, linked: None | dict = None):
        self.idx = idx
        self.name = name
        self.obj_type = obj_type
        self.linked = linked
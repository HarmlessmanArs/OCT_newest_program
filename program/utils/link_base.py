class LinkBase:
    def __init__(self, link_name: str, link_idx: int, obj_type: str, linked: dict | None):
        self.link_name = link_name
        self.link_idx = link_idx
        self.obj_type = obj_type
        self.linked = linked
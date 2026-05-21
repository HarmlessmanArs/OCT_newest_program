class SaveModule:
    def can_handle(self, block) -> bool:
        raise NotImplementedError

    def save(self, block, writer):
        raise NotImplementedError


class LoadModule:
    def can_handle(self, handle) -> bool:
        raise NotImplementedError

    def load(self, handle, reader):
        raise NotImplementedError
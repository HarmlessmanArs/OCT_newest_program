class LazyArray:
    def __init__(self, handle, loader):
        self.handle = handle
        self.loader = loader
        self._data = None

    def get(self):
        if self._data is None:
            self._data = self.loader.load(self.handle)
        return self._data
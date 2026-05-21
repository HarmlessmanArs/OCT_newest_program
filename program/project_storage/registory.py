class BlockRegistry:
    def __init__(self):
        self.save_modules = []
        self.load_modules = []

    def register(self, save_module, load_module):
        self.save_modules.append(save_module)
        self.load_modules.append(load_module)

    def get_saver(self, block):
        for m in self.save_modules:
            if m.can_handle(block):
                return m
        raise ValueError(f"No saver for block type {block.type}")

    def get_loader(self, handle):
        for m in self.load_modules:
            if m.can_handle(handle):
                return m
        raise ValueError(f"No loader for {handle.loader_type}")
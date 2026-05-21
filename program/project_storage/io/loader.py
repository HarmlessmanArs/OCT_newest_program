from ..core.project import Project
from ..core.dataset import Dataset
from ..core.datablock import DataBlock
from ..core.handles import DataHandle
from .reader import ZipReader
from ..lazy.lazy_array import LazyArray


class ProjectLoader:

    def __init__(self, registry):
        self.registry = registry

    def load(self, path):
        reader = ZipReader(path)

        manifest = reader.read_json("manifest.json")
        project = Project(version=manifest["version"])

        for ds_entry in manifest["datasets"]:
            ds = Dataset(ds_entry["id"], ds_entry["name"])

            for b in ds_entry["blocks"]:
                handle = DataHandle(
                    path=b["path"],
                    loader_type=b["loader"]
                )

                loader = self.registry.get_loader(handle)
                lazy = LazyArray(handle, loader)

                block = DataBlock(
                    name=b["name"],
                    type=b["type"],
                    handle=handle,
                    meta={"lazy": lazy}
                )

                ds.add_block(block)

            project.add_dataset(ds)

        reader.close()
        return project
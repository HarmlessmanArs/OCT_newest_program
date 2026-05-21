from .writer import ZipWriter


class ProjectSaver:

    def __init__(self, registry):
        self.registry = registry

    def save(self, project, path):
        writer = ZipWriter(path)

        manifest = {
            "version": project.version,
            "datasets": []
        }

        for ds in project.datasets:
            ds_entry = {
                "id": ds.id,
                "name": ds.name,
                "blocks": []
            }

            for block in ds.blocks.values():
                saver = self.registry.get_saver(block)
                saver.save(block, writer)

                ds_entry["blocks"].append({
                    "name": block.name,
                    "type": block.type,
                    "path": block.handle.path,
                    "loader": block.handle.loader_type
                })

            manifest["datasets"].append(ds_entry)

        writer.write_json("manifest.json", manifest)
        writer.close()
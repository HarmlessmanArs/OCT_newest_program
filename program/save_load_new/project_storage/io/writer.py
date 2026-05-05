import json
import numpy as np
from zipfile import ZipFile
import io


class ZipWriter:
    def __init__(self, path):
        self.zip = ZipFile(path, "w")

    def write_json(self, path, data):
        self.zip.writestr(path, json.dumps(data, indent=2))

    def write_npy(self, path, array):
        buffer = io.BytesIO()
        np.save(buffer, array)
        self.zip.writestr(path, buffer.getvalue())

    def close(self):
        self.zip.close()
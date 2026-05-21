import json
import numpy as np
from zipfile import ZipFile
import io


class ZipReader:
    def __init__(self, path):
        self.zip = ZipFile(path, "r")

    def read_json(self, path):
        with self.zip.open(path) as f:
            return json.load(f)

    def read_npy(self, path):
        with self.zip.open(path) as f:
            return np.load(io.BytesIO(f.read()))

    def close(self):
        self.zip.close()
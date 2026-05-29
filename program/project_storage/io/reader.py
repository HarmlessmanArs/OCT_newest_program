import zarr
from zarr.storage import ZipStore
from pathlib import Path
from ..lazy.lazy_array import LazyBmipArray


class ProjectReader:
    """Интерфейс для навигации и ленивой загрузки данных из файлов .bmip (Zarr 3.2.1+)"""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.store = None
        self.root = None

        if not self.file_path.exists():
            raise FileNotFoundError(f"Файл проекта не найден по пути: {self.file_path}")

    def open(self):
        """Открывает ZipStore архива на чтение."""
        print(f"  [DEBUG READER] Открытие файла на чтение: {self.file_path}")
        self.store = ZipStore(str(self.file_path), mode='r')
        self.root = zarr.open_group(store=self.store, mode='r')
        print(f"  [DEBUG READER] ZipStore успешно открыт. Группы в корне: {list(self.root.keys())}")

    def get_structure_and_meta(self) -> dict:
        """Возвращает глобальный скелет проекта для дерева QTreeWidget и менеджмента окон"""
        self._check_connection()

        # Логируем, какие вообще атрибуты физически записаны в корне Zarr
        all_attrs = list(self.root.attrs.keys())
        print(f"  [DEBUG READER] Чтение атрибутов корня. Доступные ключи в файле: {all_attrs}")

        # ФИКС: Читаем не только старое дерево, но и новые плоские структуры!
        meta_data = {
            'project_meta': self.root.attrs.get('project_meta', {}),
            'tree_structure': self.root.attrs.get('tree_structure', {}),
            'hierarchy': self.root.attrs.get('hierarchy', []),
            'widgets': self.root.attrs.get('widgets', {}),
            'workspace': self.root.attrs.get('workspace', {})
        }

        print(
            f"  [DEBUG READER] Вычитано из файла: папок={len(meta_data['hierarchy'])}, окон={len(meta_data['widgets'])}")
        return meta_data

    def get_datablock_meta(self, block_uuid: str) -> dict:
        """Получает текстовые метаданные папки (pixel size, object features)"""
        self._check_connection()
        try:
            block = self.root[f"blocks/{block_uuid}"]
            return {
                'metadata': block.attrs.get('metadata', {}),
                'data_information': block.attrs.get('data_information', {})
            }
        except KeyError:
            print(f"  [DEBUG READER] ⚠️ Группа blocks/{block_uuid} не найдена в файле!")
            return {}

    def get_lazy_array(self, block_uuid: str, category: str, item_uuid: str) -> LazyBmipArray | None:
        """Возвращает ленивый прокси-массив для тяжелых графических данных или скрытых слоев"""
        self._check_connection()
        dataset_path = f"blocks/{block_uuid}/{category}/{item_uuid}"
        if dataset_path in self.root:
            return LazyBmipArray(self.store, dataset_path)
        return None

    def get_graph_data(self, block_uuid: str, graph_uuid: str) -> dict | None:
        """Восстанавливает массивы точек осей и настроек графиков"""
        self._check_connection()
        path = f"blocks/{block_uuid}/graphs/{graph_uuid}"
        if path not in self.root:
            return None

        g_group = self.root[path]
        return {
            'x': g_group['x'][:] if 'x' in g_group else None,
            'y': g_group['y'][:] if 'y' in g_group else None,
            'settings': g_group.attrs.get('settings', {})
        }

    def get_parameter_calculation(self, block_uuid: str) -> dict:
        """Возвращает структурированный блок расчетов: non_array-параметры и ленивые ссылки на array-карты"""
        self._check_connection()
        path = f"blocks/{block_uuid}/parameter_calculation"
        if path not in self.root:
            return {'non_array': {}, 'array': {}}

        p_group = self.root[path]
        result = {
            'non_array': p_group.attrs.get('non_array', {}),
            'array': {}
        }

        if 'array' in p_group:
            array_group = p_group['array']
            for item_uuid in array_group.keys():
                result['array'][item_uuid] = LazyBmipArray(self.store, f"{path}/array/{item_uuid}")

        return result

    def _check_connection(self):
        if self.root is None:
            raise RuntimeError("Попытка чтения. Файл проекта .bmip не был открыт через open()")

    def close(self):
        """Освобождает ZIP-архив на диске."""
        if self.store:
            print("  [DEBUG READER] Закрытие ZipStore.")
            self.store.close()
            self.store = None
            self.root = None
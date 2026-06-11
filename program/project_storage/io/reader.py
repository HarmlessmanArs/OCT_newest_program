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
        """Возвращает глобальный скелет проекта для дерева QTreeWidget и менеджмента окон,
        включая прокси-объекты для изображений."""
        self._check_connection()

        all_attrs = list(self.root.attrs.keys())
        print(f"  [DEBUG READER] Чтение атрибутов корня. Доступные ключи: {all_attrs}")

        meta_data = {
            'project_meta': self.root.attrs.get('project_meta', {}),
            'tree_structure': self.root.attrs.get('tree_structure', {}),
            'hierarchy': self.root.attrs.get('hierarchy', []),
            'widgets': self.root.attrs.get('widgets', {}),
            'workspace': self.root.attrs.get('workspace', {}),
            'blocks': {}
        }

        root_keys = list(self.root.keys())
        print(f"  [DEBUG READER] Папки в корне архива: {root_keys}")

        if 'blocks' in root_keys:
            blocks_group = self.root['blocks']
            block_uuids = list(blocks_group.keys())
            print(f"  [DEBUG READER] Найдено UUID датаблоков: {block_uuids}")

            for block_uuid in block_uuids:
                block_content = blocks_group[block_uuid]

                # Убрали жесткую проверку isinstance(..., zarr.Group)!
                # Zarr 3.x может оборачивать группы в свои прокси-классы. Проверяем просто наличие .keys()
                if not hasattr(block_content, 'keys'):
                    print(f"  [DEBUG READER] ⚠️ {block_uuid} не является группой (нет метода keys). Пропуск.")
                    continue

                block_keys = list(block_content.keys())
                print(f"  [DEBUG READER] Внутри блока {block_uuid} найдены папки: {block_keys}")

                block_dict = {
                    "metadata": block_content.attrs.get('metadata', {}),
                    "data_information": block_content.attrs.get('data_information', {}),
                    "original_images": {},
                    "boundaries_images": {},
                    "mu_t_images": {},
                    "tables": {},
                }

                if 'original_images' in block_keys:
                    imgs_group = block_content['original_images']
                    img_keys = list(imgs_group.keys())
                    print(f"  [DEBUG READER] 📸 В original_images найдено файлов: {len(img_keys)} -> {img_keys}")

                    for img_uuid in img_keys:
                        z_array = imgs_group[img_uuid]

                        # Безопасное чтение атрибутов
                        try:
                            attrs_dict = dict(z_array.attrs)
                            img_name = attrs_dict.get("name", f"Image_{img_uuid[:8]}")
                        except Exception as e:
                            print(f"  [DEBUG READER] ⚠️ Ошибка чтения атрибутов для {img_uuid}: {e}")
                            img_name = f"Image_{img_uuid[:8]}"

                        print(f"  [DEBUG READER] Готовим прокси для: {img_name} ({img_uuid})")

                        lazy_arr = LazyBmipArray(self.file_path, f"blocks/{block_uuid}/original_images/{img_uuid}")

                        block_dict["original_images"][img_uuid] = {
                            "name": img_name,
                            "data": lazy_arr
                        }
                else:
                    print(f"  [DEBUG READER] ⚠️ Папка 'original_images' отсутствует в {block_uuid}!")

                meta_data['blocks'][block_uuid] = block_dict

        print(
            f"  [DEBUG READER] ИТОГО Вычитано: папок={len(meta_data['hierarchy'])}, окон={len(meta_data['widgets'])}, блоков={len(meta_data['blocks'])}")
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
            return LazyBmipArray(self.file_path, dataset_path)
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
                result['array'][item_uuid] = LazyBmipArray(self.file_path, f"{path}/array/{item_uuid}")

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
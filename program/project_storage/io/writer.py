import zarr
from zarr.storage import ZipStore
import numpy as np
from pathlib import Path


class ProjectWriter:
    """Класс для сериализации и физической записи структуры проекта в формат .bmip (Zarr 3.2.1+)"""

    def __init__(self, target_path: Path):
        self.target_path = Path(target_path)

    def write(self, snapshot: dict, progress_callback=None):
        """
        Принимает snapshot проекта и записывает его во временный файл,
        после чего атомарно заменяет целевой файл на диске.
        """
        tmp_path = self.target_path.with_suffix('.bmip.tmp')
        store = None

        try:
            # В Zarr 3.x ZipStore находится в подмодуле zarr.storage
            store = ZipStore(str(tmp_path), mode='w')

            # Открываем корневую группу через верхнеуровневый API Zarr 3
            root = zarr.open_group(store=store)

            # 1. Глобальные метаданные проекта и скелет QTreeWidget
            root.attrs['project_meta'] = snapshot.get('project_meta', {})
            root.attrs['tree_structure'] = snapshot.get('tree_structure', {})

            # 2. Запись датаблоков (datablocks)
            blocks_data = snapshot.get('blocks', {})

            # Так как мы пишем пустой ZIP с нуля, используем исключительно create_group
            blocks_group = root.create_group('blocks')

            total_blocks = len(blocks_data)
            for idx, (block_uuid, block_content) in enumerate(blocks_data.items()):
                self._write_datablock(blocks_group, str(block_uuid), block_content)

                if progress_callback:
                    progress_callback(int(((idx + 1) / max(total_blocks, 1)) * 100))

            # КРИТИЧЕСКИ ВАЖНО для Zarr 3.x: явно закрываем ZipStore,
            # чтобы финализировать ZIP-структуру на жестком диске!
            store.close()

            # 3. Атомарная замена файла на диске
            if self.target_path.exists():
                self.target_path.unlink()
            tmp_path.rename(self.target_path)

        except Exception as e:
            if store:
                store.close()
            if tmp_path.exists():
                tmp_path.unlink()
            raise RuntimeError(f"Критическая ошибка при записи .bmip: {str(e)}")

    def _write_datablock(self, parent_group: zarr.Group, block_uuid: str, content: dict):
        """Запись отдельного Datablock со всей внутренней иерархией"""
        block_group = parent_group.create_group(block_uuid)

        # Запись текстовой информации и особенностей объекта в атрибуты группы
        block_group.attrs['metadata'] = content.get('metadata', {})
        block_group.attrs['data_information'] = content.get('data_information', {})

        # --- Визуальные категории (Каналы отображения ОКТ) ---
        visual_categories = ['original_images', 'boundaries_images', 'mu_t_images', 'tables']
        for cat in visual_categories:
            if cat in content and content[cat]:
                cat_group = block_group.create_group(cat)
                for item_uuid, array_data in content[cat].items():
                    self._save_heavy_array(cat_group, str(item_uuid), array_data)

        # --- Категория Графиков ---
        if 'graphs' in content and content['graphs']:
            graphs_group = block_group.create_group('graphs')
            for graph_uuid, graph_data in content['graphs'].items():
                g_node = graphs_group.create_group(str(graph_uuid))

                # Сохраняем оси X и Y как отдельные массивы
                if 'x' in graph_data:
                    self._save_heavy_array(g_node, 'x', graph_data['x'])
                if 'y' in graph_data:
                    self._save_heavy_array(g_node, 'y', graph_data['y'])

                # Стили отображения сохраняем в атрибуты
                g_node.attrs['settings'] = graph_data.get('settings', {})

        # --- Категория Скрытых Данных (Hidden Data) ---
        if 'hidden_data' in content and content['hidden_data']:
            hidden_group = block_group.create_group('hidden_data')
            for item_uuid, hidden_payload in content['hidden_data'].items():
                # Автоматически обрабатываем "рваные" списки границ разной длины
                if isinstance(hidden_payload, list) and hidden_payload and isinstance(hidden_payload[0], list):
                    hidden_payload = self._pad_jagged_list(hidden_payload)

                self._save_heavy_array(hidden_group, str(item_uuid), hidden_payload)

        # --- Модуль Расчета Параметров (Parameter Calculation) ---
        if 'parameter_calculation' in content:
            param_group = block_group.create_group('parameter_calculation')
            p_content = content['parameter_calculation']

            # Разделение по физическому типу: Non-Array (скаляры v1/v2/v3, средние по образцу)
            param_group.attrs['non_array'] = p_content.get('non_array', {})

            # Array данные (1D профили угасания рассеяния, 2D/3D карты маппинга параметров)
            if 'array' in p_content and p_content['array']:
                array_param_group = param_group.create_group('array')
                for item_uuid, array_data in p_content['array'].items():
                    self._save_heavy_array(array_param_group, str(item_uuid), array_data)

    def _save_heavy_array(self, parent_group: zarr.Group, name: str, data):
        """Сохранение NumPy массивов через валидный для Zarr 3.x метод create_array"""
        if not isinstance(data, np.ndarray):
            data = np.array(data)

        if data.size == 0:
            return

        # Интеллектуальный расчет чанков по размерностям
        if data.ndim == 3:
            # Для 3D ОКТ-объемов: нарезаем послойно (1 B-скан = 1 чанк)
            chunks = (1, data.shape[1], data.shape[2])
        elif data.ndim == 2:
            # Для больших 2D карт параметров или таблиц границ
            chunks = (max(1, data.shape[0] // 10), data.shape[1])
        else:
            # Для 1D векторов отдаем автоматический расчет чанков на усмотрение Zarr 3
            chunks = None

            # Используем легитимный метод create_array.
        # Передавать строковый тип dtype безопаснее для внутренней валидации Zarr 3.
        parent_group.create_array(
            name=name,
            shape=data.shape,
            dtype=str(data.dtype),
            data=data,
            chunks=chunks
        )

    def _pad_jagged_list(self, jagged_list: list) -> np.ndarray:
        """Превращает 'рваный' список координат в прямоугольную матрицу с NaN"""
        max_len = max(len(row) for row in jagged_list)
        padded = np.full((len(jagged_list), max_len), np.nan, dtype=np.float32)
        for i, row in enumerate(jagged_list):
            padded[i, :len(row)] = row
        return padded
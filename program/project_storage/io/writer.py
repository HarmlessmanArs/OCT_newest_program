import zarr
from zarr.storage import ZipStore
import numpy as np
from pathlib import Path
import warnings
import os
import time
import psutil


class ProjectWriter:
    """Класс для сериализации и физической записи структуры проекта в формат .bmip (Zarr 3.2.1+)"""

    def __init__(self, target_path: Path):
        self.target_path = Path(target_path)

    def write(self, snapshot: dict, progress_callback=None):
        tmp_path = self.target_path.with_suffix('.bmip.tmp')
        store = None

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    category=UserWarning,
                    message=".*Duplicate name:.*zarr.json.*"
                )

                print(f"  [DEBUG WRITER] Открытие ZipStore: {tmp_path}")
                store = ZipStore(str(tmp_path), mode='w')
                root = zarr.open_group(store=store)

                # АНАЛИЗ И ЗАПИСЬ МЕТАДАННЫХ КОРНЯ
                print(f"  [DEBUG WRITER] Ключи, пришедшие в Writer: {list(snapshot.keys())}")

                # Собираем все корневые метаданные, поддерживая старый и новый формат
                root_attributes = {
                    'project_meta': snapshot.get('project_meta', {}),
                    'tree_structure': snapshot.get('tree_structure', {}),
                    # ОБЯЗАТЕЛЬНО ДОБАВЛЯЕМ НОВЫЕ ПОЛЯ В ФАЙЛ СОХРАНЕНИЯ:
                    'hierarchy': snapshot.get('hierarchy', []),
                    'widgets': snapshot.get('widgets', {}),
                    'workspace': snapshot.get('workspace', {})
                }

                print(f"  [DEBUG WRITER] Запись корневых атрибутов в Zarr...")
                print(f"    - hierarchy (папок): {len(root_attributes['hierarchy'])}")
                print(f"    - widgets (окон): {len(root_attributes['widgets'])}")

                root.attrs.update(root_attributes)

                # 2. Запись датаблоков (datablocks)
                blocks_data = snapshot.get('blocks', {})
                print(f"  [DEBUG WRITER] Найдено тяжелых блоков данных (blocks): {len(blocks_data)}")

                blocks_group = root.create_group('blocks')
                total_blocks = len(blocks_data)

                for idx, (block_uuid, block_content) in enumerate(blocks_data.items()):
                    print(f"  [DEBUG WRITER] Запись блока данных: {block_uuid}")
                    self._write_datablock(blocks_group, str(block_uuid), block_content)

                    if progress_callback:
                        progress_callback(int(((idx + 1) / max(total_blocks, 1)) * 100))

                print("  [DEBUG WRITER] Закрытие ZipStore и финализация ZIP...")
                store.close()
                proc = psutil.Process(os.getpid())

                print("=== OPEN FILES ===")
                for f in proc.open_files():
                    if ".bmip" in f.path.lower():
                        print(f.path)
                # --- ИСПРАВЛЕННЫЙ БЛОК АТОМАРНОЙ ЗАМЕНЫ ---
                max_retries = 5
                success = False

                for attempt in range(max_retries):
                    try:
                        # target = str(self.target_path)
                        #
                        # for proc in psutil.process_iter(['pid', 'name']):
                        #     try:
                        #         for f in proc.open_files():
                        #             if target.lower() in f.path.lower():
                        #                 print(
                        #                     f"HOLDER PID={proc.pid} "
                        #                     f"NAME={proc.name()} "
                        #                     f"FILE={f.path}"
                        #                 )
                        #     except Exception:
                        #         pass
                        os.replace(tmp_path, self.target_path)
                        print(f"  [DEBUG WRITER] Файл успешно заменен: {self.target_path}")
                        success = True
                        break
                    except PermissionError as e:
                        if attempt < max_retries - 1:
                            print(f"  [DEBUG WRITER] Файл занят, повтор {attempt + 1}/{max_retries}...")
                            time.sleep(0.2)  # Ждем 200 мс перед следующей попыткой
                            continue
                        else:
                            print(f"  [DEBUG WRITER] ❌ Ошибка атомарной замены после {max_retries} попыток: {e}")
                            # Если все попытки провалены, очищаем временный файл, чтобы не оставлять мусор
                            if tmp_path.exists():
                                try:
                                    tmp_path.unlink()
                                except:
                                    pass
                            raise RuntimeError(f"Критическая ошибка при записи .bmip: {str(e)}")

                # # 3. Атомарная замена файла на диске
                # if self.target_path.exists():
                #     self.target_path.unlink()
                # tmp_path.rename(self.target_path)
                # print(f"  [DEBUG WRITER] Временный файл успешно переименован в {self.target_path}")

        except Exception as e:
            if store:
                store.close()
            if tmp_path.exists():
                tmp_path.unlink()
            print(f"  [DEBUG WRITER] ❌ ОШИБКА ВНУТРИ ПИСАТЕЛЯ: {str(e)}")
            raise RuntimeError(f"Критическая ошибка при записи .bmip: {str(e)}")

    def _write_datablock(self, parent_group: zarr.Group, block_uuid: str, content: dict):
        """Запись отдельного Datablock со всей внутренней иерархией"""
        block_group = parent_group.create_group(block_uuid)

        block_group.attrs.update({
            'metadata': content.get('metadata', {}),
            'data_information': content.get('data_information', {})
        })

        visual_categories = ['original_images', 'boundaries_images', 'mu_t_images', 'tables']
        for cat in visual_categories:
            if cat in content and content[cat]:
                cat_group = block_group.create_group(cat)
                for item_uuid, array_data in content[cat].items():
                    self._save_heavy_array(cat_group, str(item_uuid), array_data)

        if 'graphs' in content and content['graphs']:
            graphs_group = block_group.create_group('graphs')
            for graph_uuid, graph_data in content['graphs'].items():
                g_node = graphs_group.create_group(str(graph_uuid))
                if 'x' in graph_data:
                    self._save_heavy_array(g_node, 'x', graph_data['x'])
                if 'y' in graph_data:
                    self._save_heavy_array(g_node, 'y', graph_data['y'])
                g_node.attrs['settings'] = graph_data.get('settings', {})

        if 'hidden_data' in content and content['hidden_data']:
            hidden_group = block_group.create_group('hidden_data')
            for item_uuid, hidden_payload in content['hidden_data'].items():
                if isinstance(hidden_payload, list) and hidden_payload and isinstance(hidden_payload[0], list):
                    hidden_payload = self._pad_jagged_list(hidden_payload)
                self._save_heavy_array(hidden_group, str(item_uuid), hidden_payload)

        if 'parameter_calculation' in content:
            param_group = block_group.create_group('parameter_calculation')
            p_content = content['parameter_calculation']
            param_group.attrs['non_array'] = p_content.get('non_array', {})

            if 'array' in p_content and p_content['array']:
                array_param_group = param_group.create_group('array')
                for item_uuid, array_data in p_content['array'].items():
                    self._save_heavy_array(array_param_group, str(item_uuid), array_data)

    @staticmethod
    def _save_heavy_array(parent_group: zarr.Group, name: str, data):
        # 1. Извлекаем реальный массив и метаданные, если к нам пришел словарь
        metadata = {}
        if isinstance(data, dict):
            actual_array = data.get("data")
            # Сохраняем остальные ключи (например, "name") как метаданные
            metadata = {k: v for k, v in data.items() if k != "data"}
        else:
            actual_array = data

        # Защита от пустых данных (если data в словаре был None)
        if actual_array is None:
            return

        # ФИКС: Если это ленивый массив из загруженного проекта, выгружаем его полностью!
        if hasattr(actual_array, 'load_fully'):
            actual_array = actual_array.load_fully()

        # Теперь безопасно приводим к numpy, зная, что это реальные данные, а не словарь
        if not isinstance(actual_array, np.ndarray):
            actual_array = np.array(actual_array)

        if actual_array.size == 0:
            return

        if actual_array.ndim == 3:
            chunks = (1, actual_array.shape[1], actual_array.shape[2])
        elif actual_array.ndim == 2:
            chunks = (max(1, actual_array.shape[0] // 10), actual_array.shape[1])
        else:
            chunks = None

        # 2. Создаем массив Zarr (используем только извлеченный actual_array)
        z_array = parent_group.create_array(
            name=name,
            data=actual_array,
            chunks=chunks
        )

        # 3. Записываем метаданные ("name" и др.) в атрибуты Zarr-массива
        for meta_key, meta_value in metadata.items():
            z_array.attrs[meta_key] = meta_value

    @staticmethod
    def _pad_jagged_list(jagged_list: list) -> np.ndarray:
        max_len = max(len(row) for row in jagged_list)
        padded = np.full((len(jagged_list), max_len), np.nan, dtype=np.float32)
        for i, row in enumerate(jagged_list):
            padded[i, :len(row)] = row
        return padded

from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from .reader import ProjectReader


class LoadProjectWorker(QThread):
    """
    Поток для фонового открытия и первичного парсинга проекта .bmip.
    Не блокирует GUI PyQt6 во время чтения диска.
    """
    # Передает: (Успех: bool, Данные_или_Ошибка: dict | str, Экземпляр_Reader: ProjectReader | None)
    finished = pyqtSignal(bool, object, object)
    progress = pyqtSignal(int)

    def __init__(self, file_path: str | Path):
        super().__init__()
        self.file_path = Path(file_path)

    def run(self):
        reader = None
        try:
            self.progress.emit(10)
            # 1. Инициализируем и открываем ридер (Zarr 3.2.1 ZipStore)
            reader = ProjectReader(self.file_path)
            reader.open()
            self.progress.emit(30)

            # 2. Считываем глобальный скелет для QTreeWidget
            base_meta = reader.get_structure_and_meta()
            tree_structure = base_meta.get('tree_structure', {})

            self.progress.emit(50)

            # 3. Реконструируем snapshot проекта в памяти (только метаданные и ленивые ссылки)
            snapshot = {
                'project_meta': base_meta.get('project_meta', {}),
                'tree_structure': tree_structure,
                'blocks': {}
            }

            # Обходим дерево датаблоков, которое сохранил writer
            if 'blocks' in reader.root:
                blocks_group = reader.root['blocks']
                block_uuids = list(blocks_group.keys())
                total_blocks = len(block_uuids)

                for idx, block_uuid in enumerate(block_uuids):
                    # Собираем текстовые особенности объекта
                    block_meta = reader.get_datablock_meta(block_uuid)

                    snapshot['blocks'][block_uuid] = {
                        'metadata': block_meta.get('metadata', {}),
                        'data_information': block_meta.get('data_information', {}),
                        'original_images': {},
                        'boundaries_images': {},
                        'mu_t_images': {},
                        'tables': {},
                        'graphs': {},
                        'hidden_data': {},
                        'parameter_calculation': {'non_array': {}, 'array': {}}
                    }

                    # Наполняем ленивыми ссылками существующие категории
                    b_path = f"blocks/{block_uuid}"

                    for cat in ['original_images', 'boundaries_images', 'mu_t_images', 'tables', 'hidden_data']:
                        if f"{b_path}/{cat}" in reader.root:
                            for item_uuid in reader.root[f"{b_path}/{cat}"].keys():
                                # Получаем прокси-объект, массив в RAM не грузится!
                                snapshot['blocks'][block_uuid][cat][item_uuid] = reader.get_lazy_array(
                                    block_uuid, cat, item_uuid
                                )

                    # Восстанавливаем графики (оси небольшие, их можно подгрузить сразу)
                    if f"{b_path}/graphs" in reader.root:
                        for graph_uuid in reader.root[f"{b_path}/graphs"].keys():
                            snapshot['blocks'][block_uuid]['graphs'][graph_uuid] = reader.get_graph_data(
                                block_uuid, graph_uuid
                            )

                    # Восстанавливаем модуль расчетов параметров (Array / Non-Array)
                    if f"{b_path}/parameter_calculation" in reader.root:
                        calc_data = reader.get_parameter_calculation(block_uuid)
                        snapshot['blocks'][block_uuid]['parameter_calculation'] = calc_data

                    # Обновляем прогресс
                    current_prog = 50 + int(((idx + 1) / max(total_blocks, 1)) * 40)
                    self.progress.emit(current_prog)

            self.progress.emit(100)
            # Возвращаем успех, собранный snapshot и открытый ридер
            self.finished.emit(True, snapshot, reader)

        except Exception as e:
            # Если упали на этапе открытия — закрываем архив, чтобы не блокировать файл
            if reader:
                reader.close()
            self.finished.emit(False, f"Ошибка при загрузке проекта: {str(e)}", None)
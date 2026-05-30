from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from .reader import ProjectReader


class LoadProjectWorker(QThread):
    """
    Поток для фонового открытия и первичного парсинга проекта .bmip.
    Не блокирует GUI PyQt6 во время чтения диска.
    """
    work_finished = pyqtSignal(bool, object, object)
    progress = pyqtSignal(int)

    def __init__(self, file_path: str | Path):
        super().__init__()
        self.file_path = Path(file_path)

    def run(self):
        reader = None
        try:
            print("\n" + "=" * 60)
            print("[DEBUG LOADER] >>> ЗАПУСК ПОТОКА ЗАГРУЗКИ ПРОЕКТА <<<")
            print(f"[DEBUG LOADER] Чтение файла: {self.file_path}")

            self.progress.emit(10)

            # 1. Инициализируем и открываем ридер
            reader = ProjectReader(self.file_path)
            reader.open()
            self.progress.emit(30)

            # 2. Считываем глобальные метаданные и структуры
            print("[DEBUG LOADER] Вызов reader.get_structure_and_meta()...")
            base_meta = reader.get_structure_and_meta()
            self.progress.emit(50)

            # 3. ФИКС: Собираем полный snapshot, включая новые плоские структуры
            snapshot = {
                'project_meta': base_meta.get('project_meta', {}),
                'tree_structure': base_meta.get('tree_structure', {}),
                # ДОБАВЛЯЕМ НОВЫЕ КЛЮЧИ:
                'hierarchy': base_meta.get('hierarchy', []),
                'widgets': base_meta.get('widgets', {}),
                'workspace': base_meta.get('workspace', {}),
                'blocks': {}
            }

            print("[DEBUG LOADER] Скелет снапшота сформирован в памяти.")
            print(f"  - Папок в снапшоте: {len(snapshot['hierarchy'])}")
            print(f"  - Окон в снапшоте: {len(snapshot['widgets'])}")

            # 4. Обходим дерево датаблоков (тяжелых массивов)
            if 'blocks' in reader.root:
                blocks_group = reader.root['blocks']
                block_uuids = list(blocks_group.keys())
                total_blocks = len(block_uuids)
                print(f"[DEBUG LOADER] Обнаружено тяжелых блоков данных (blocks): {total_blocks}")

                for idx, block_uuid in enumerate(block_uuids):
                    print(f"[DEBUG LOADER] Ликуем метаданные блока: {block_uuid}")
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

                    b_path = f"blocks/{block_uuid}"

                    # Проксирование массивов
                    for cat in ['original_images', 'boundaries_images', 'mu_t_images', 'tables', 'hidden_data']:
                        if f"{b_path}/{cat}" in reader.root:
                            for item_uuid in reader.root[f"{b_path}/{cat}"].keys():
                                snapshot['blocks'][block_uuid][cat][item_uuid] = reader.get_lazy_array(
                                    block_uuid, cat, item_uuid
                                )

                    # Восстановление графиков
                    if f"{b_path}/graphs" in reader.root:
                        for graph_uuid in reader.root[f"{b_path}/graphs"].keys():
                            snapshot['blocks'][block_uuid]['graphs'][graph_uuid] = reader.get_graph_data(
                                block_uuid, graph_uuid
                            )

                    # Восстановление модулей расчетов
                    if f"{b_path}/parameter_calculation" in reader.root:
                        calc_data = reader.get_parameter_calculation(block_uuid)
                        snapshot['blocks'][block_uuid]['parameter_calculation'] = calc_data

                    current_prog = 50 + int(((idx + 1) / max(total_blocks, 1)) * 40)
                    self.progress.emit(current_prog)
            else:
                print("[DEBUG LOADER] Тяжелые блоки данных (blocks) отсутствуют в файле.")

            self.progress.emit(100)
            print("[DEBUG LOADER] >>> ПОТОК ЗАГРУЗКИ СФОРМИРОВАЛ СНАПШОТ УСПЕШНО <<<")
            print("=" * 60 + "\n")

            self.work_finished.emit(True, snapshot, reader)

        except Exception as e:
            print(f"[DEBUG LOADER] ❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ПОДГОТОВКЕ СНАПШОТА: {str(e)}")
            import traceback
            traceback.print_exc()
            if reader:
                reader.close()
            print("=" * 60 + "\n")
            self.work_finished.emit(False, f"Ошибка при загрузке проекта: {str(e)}", None)
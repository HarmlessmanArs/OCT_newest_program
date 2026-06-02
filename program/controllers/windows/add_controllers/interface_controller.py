import re
from collections import defaultdict
from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QStandardItem


class InterfaceController(QObject):
    """
    Отвечает исключительно за реставрацию и пересборку графического интерфейса
    (дерево проекта QTreeView и зона MDI) на основе актуального ProjectState.
    """

    def __init__(self, main_window, project_state, widget_factory):
        super().__init__(main_window)
        self.win = main_window
        self.state = project_state
        self.factory = widget_factory
        self.state.sig_project_loaded.connect(self.rebuild_interface)

    def rebuild_interface(self):
        """Полная пересборка графического интерфейса ТОЛЬКО при загрузке."""
        self.win.statusBar().showMessage("Обновление интерфейса...")

        # 1. Жесткая блокировка всех сигналов UI перед перестройкой
        self.win.file_info.blockSignals(True)
        self.win.widgets_area.blockSignals(True)
        self.win.tree_model.blockSignals(True)

        try:
            # === ЭТАП 1: ПОЛНАЯ ОЧИСТКА ===
            self.win.tree_model.clear()
            self.win.tree_model.setHorizontalHeaderLabels(["Project Files"])

            if hasattr(self.win, 'clear_mdi_area_safely'):
                self.win.clear_mdi_area_safely()

            # Очищаем реестр рантайма от старых UUID
            if hasattr(self.win, 'runtime_registry') and hasattr(self.win.runtime_registry, 'clear'):
                self.win.runtime_registry.clear()

            # === ЭТАП 2: ИЗВЛЕЧЕНИЕ ДАННЫХ ===
            project_data = self.state.project_data
            hierarchy = project_data.get('hierarchy', [])
            widgets_dict = project_data.get('widgets', {})

            if not hierarchy and not widgets_dict:
                self.win.statusBar().showMessage("Открыт пустой проект", 5000)
                return

            # === ЭТАП 3: ВОССТАНОВЛЕНИЕ ПАПОК ===
            created_folders_map = {}
            root_item = self.win.tree_model.invisibleRootItem()

            # Сбрасываем счетчики
            self.win.folder_count = 1
            self.win.gallery_count = 1
            self.win.graph_count = 1
            self.win.table_count = 1

            for node in hierarchy:
                if node.get('type') == 'folder':
                    f_uuid = node.get('uuid')
                    f_text = node.get('text', 'Folder')

                    # Умное обновление счетчика папок
                    folder_match = re.search(r'Folder(?:_|\s)(\d+)', f_text)
                    if folder_match:
                        self.win.folder_count = max(self.win.folder_count, int(folder_match.group(1)) + 1)

                    # Создаем ГАРАНТИРОВАННО живой элемент
                    folder_item = QStandardItem(f_text)
                    folder_item.setData(f_uuid, Qt.ItemDataRole.UserRole)
                    root_item.appendRow(folder_item)

                    # Сохраняем ссылку для виджетов
                    created_folders_map[f_uuid] = folder_item

            # === ЭТАП 4: ВОССТАНОВЛЕНИЕ ОКОН ===
            for w_uuid, descriptor in widgets_dict.items():
                parent_uuid = descriptor.get("parent_block_uuid")
                title = descriptor.get("title", "")

                # Умное обновление счетчиков виджетов
                if "Gallery" in title:
                    match = re.search(r'Gallery(?:_|\s)(\d+)', title)
                    if match: self.win.gallery_count = max(self.win.gallery_count, int(match.group(1)) + 1)
                elif "Graph" in title:
                    match = re.search(r'Graph(?:_|\s)(\d+)', title)
                    if match: self.win.graph_count = max(self.win.graph_count, int(match.group(1)) + 1)
                elif "Table" in title:
                    match = re.search(r'Table(?:_|\s)(\d+)', title)
                    if match: self.win.table_count = max(self.win.table_count, int(match.group(1)) + 1)

                # Ищем родителя строго в нашем словаре живых папок
                parent_item = created_folders_map.get(parent_uuid)

                if not parent_item:
                    print(f"[WARN] Папка {parent_uuid} не найдена. Виджет {title} улетает в корень.")
                    parent_item = root_item

                # Отдаем живой элемент Фабрике
                self.factory.restore_window_from_descriptor(descriptor, parent_item)

            # === ЭТАП 5: ФИНАЛИЗАЦИЯ И ГЕОМЕТРИЯ ===
            self.win.file_info.expandAll()

            if hasattr(self.win, 'update_window_title'):
                self.win.update_window_title()

            # Тот самый вызов геометрии, который мы добавили ранее
            if hasattr(self, '_restore_workspace_geometry'):
                self._restore_workspace_geometry()

            self.win.statusBar().showMessage("Интерфейс успешно восстановлен", 5000)

        except Exception as e:
            self.win.statusBar().showMessage("Ошибка при сборке интерфейса", 5000)
            import traceback
            traceback.print_exc()

        finally:
            # Гарантированное снятие блокировок
            self.win.file_info.blockSignals(False)
            self.win.widgets_area.blockSignals(False)
            self.win.tree_model.blockSignals(False)

    def _build_tree_nodes_from_hierarchy(self, parent_item, parent_uuid, parent_to_children):
        """Рекурсивно строит иерархию интерфейса на основе плоской карты связей."""
        children = parent_to_children.get(parent_uuid, [])

        for child in children:
            node_uuid = child.get('uuid')
            node_text = child.get('text', 'Без названия')
            node_type = child.get('type')

            if node_type == 'folder':
                tree_item = QStandardItem(node_text)
                if node_uuid:
                    tree_item.setData(node_uuid, Qt.ItemDataRole.UserRole)
                parent_item.appendRow(tree_item)

                # Рекурсивный спуск
                self._build_tree_nodes_from_hierarchy(tree_item, node_uuid, parent_to_children)
            else:
                widgets_dict = self.state.project_data.get("widgets", {})
                descriptor = widgets_dict.get(node_uuid)
                if descriptor:
                    self.factory.restore_window_from_descriptor(descriptor, parent_item)

    def _restore_workspace_geometry(self):
        """Применяет сохраненную геометрию и фокус с подробной отладкой."""
        print("\n[DEBUG INTERFACE] >>> Запуск финального восстановления интерфейса")
        workspace = self.state.project_data.get("workspace", {})
        positions = workspace.get("mdi_positions", {})
        active_uuid = workspace.get("active_widget_uuid")

        print(f"  - Ожидаемый активный UUID из файла: {active_uuid}")

        mdi_area = getattr(self.win, 'widgets_area', None)
        if not mdi_area:
            print("  - [CRITICAL] Не найден widgets_area в главном окне!")
            return

        sub_windows = mdi_area.subWindowList()
        print(f"  - Количество окон, зарегистрированных в QMdiArea прямо сейчас: {len(sub_windows)}")

        target_active_sub = None

        for sub_window in sub_windows:
            widget = sub_window.widget()
            uuid_str = str(getattr(widget, 'uuid', ''))
            print(f"    * Проверяем живое окно MDI: '{sub_window.windowTitle()}' | UUID: {uuid_str} | Видимость: {sub_window.isVisible()}")

            if uuid_str == active_uuid:
                target_active_sub = sub_window
                print(f"      -> Матч! Это окно должно стать активным.")

        if target_active_sub:
            print(f"  - Активируем окно: '{target_active_sub.windowTitle()}'")
            mdi_area.setActiveSubWindow(target_active_sub)
            # Временный фикс для теста: принудительно покажем активное окно
            target_active_sub.show()
        else:
            print("  - [WARN] Окно с active_uuid не найдено среди живых окон или active_uuid равен None.")
        print("[DEBUG INTERFACE] <<< Завершение работы восстановления интерфейса\n")
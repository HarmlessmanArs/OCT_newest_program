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

        # Автоматическая реакция на завершение загрузки проекта
        # self.state.sig_project_loaded.connect(self.rebuild_interface)

    def rebuild_interface(self):
        """
        Полная пересборка графического интерфейса на основе паттерна Model/View.
        Синхронизирует QTreeView и QMdiArea с актуальным состоянием self.state.project_data
        """
        self.win.statusBar().showMessage("Обновление интерфейса...")

        # 1. Жесткая блокировка всех сигналов UI перед перестройкой
        self.win.file_info.blockSignals(True)
        self.win.widgets_area.blockSignals(True)
        self.win.tree_model.blockSignals(True)

        selection_model = self.win.file_info.selectionModel()
        if selection_model:
            selection_model.blockSignals(True)

        try:
            # 2. Очищаем старую визуальную модель дерева
            self.win.tree_model.clear()
            self.win.tree_model.setHorizontalHeaderLabels(["Project Files"])

            # 3. Безопасно уничтожаем окна (метод остается в MainWindow)
            if hasattr(self.win, '_clear_mdi_area_safely'):
                self.win.clear_mdi_area_safely()

            # 4. Извлекаем плоскую структуру проекта
            project_data = self.state.project_data
            hierarchy = project_data.get('hierarchy', [])

            if not hierarchy:
                self.win.statusBar().showMessage("Открыт пустой проект", 5000)
                return

            # === УМНОЕ ОБНОВЛЕНИЕ СЧЕТЧИКОВ ИМЕН ===
            self.win.folder_count = 1
            self.win.gallery_count = 1
            self.win.graph_count = 1
            self.win.table_count = 1

            for node in hierarchy:
                text = node.get('text', '')
                folder_match = re.search(r'Folder(?:_|\s)(\d+)', text)
                gallery_match = re.search(r'Gallery(?:_|\s)(\d+)', text)
                graph_match = re.search(r'Graph(?:_|\s)(\d+)', text)
                table_match = re.search(r'Table(?:_|\s)(\d+)', text)

                if folder_match:
                    self.win.folder_count = max(self.win.folder_count, int(folder_match.group(1)) + 1)
                if gallery_match:
                    self.win.gallery_count = max(self.win.gallery_count, int(gallery_match.group(1)) + 1)
                if graph_match:
                    self.win.graph_count = max(self.win.graph_count, int(graph_match.group(1)) + 1)
                if table_match:
                    self.win.table_count = max(self.win.table_count, int(table_match.group(1)) + 1)

            # 5. Строим карту связей "родитель -> список детей"
            parent_to_children = defaultdict(list)
            all_uuids = {node.get('uuid') for node in hierarchy if node.get('uuid')}

            for node in hierarchy:
                p_uuid = node.get('parent_uuid')
                if p_uuid is None or p_uuid not in all_uuids:
                    parent_to_children[None].append(node)
                else:
                    parent_to_children[p_uuid].append(node)

            # 6. Запускаем построение дерева с корня
            root_item = self.win.tree_model.invisibleRootItem()
            self._build_tree_nodes_from_hierarchy(root_item, None, parent_to_children)

            self.win.file_info.expandAll()

            if hasattr(self.win, '_update_window_title'):
                self.win.update_window_title()

            self.win.statusBar().showMessage("Интерфейс успешно восстановлен", 5000)

        except Exception as e:
            self.win.statusBar().showMessage("Ошибка при сборке интерфейса", 5000)
            raise RuntimeError(f"Сбой rebuild_interface: {str(e)}")

        finally:
            # 7. Гарантированное снятие блокировок
            self.win.file_info.blockSignals(False)
            self.win.widgets_area.blockSignals(False)
            self.win.tree_model.blockSignals(False)

            if selection_model:
                selection_model.blockSignals(False)

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
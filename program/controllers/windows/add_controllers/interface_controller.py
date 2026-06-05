from PyQt6.QtCore import QObject, Qt, QRect
from PyQt6.QtGui import QStandardItem
from ...small_controllers import UuidController


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
        self.id_controller = UuidController()
        # Слушаем сигнал успешной загрузки данных из ProjectIO/Lifecycle
        self.state.sig_project_loaded.connect(self.rebuild_interface)

    # =========================================================================
    # СБОР ДАННЫХ ПЕРЕД СОХРАНЕНИЕМ
    # =========================================================================

    def save_workspace_geometry_to_state(self):
        """
        Собирает текущие координаты, размеры и статус окон MDI.
        Пушит эти данные в ProjectState ПЕРЕД сохранением проекта.
        """
        mdi_area = getattr(self.win, 'widgets_area', None)
        if not mdi_area:
            return

        positions = {}
        active_uuid = None

        # Ищем активное окно
        active_sub = mdi_area.activeSubWindow()
        if active_sub and active_sub.widget():
            active_uuid = self.id_controller.clean_uuid(getattr(active_sub.widget(), 'uuid', ''))

        # Собираем геометрию всех живых окон
        for sub_window in mdi_area.subWindowList():
            widget = sub_window.widget()
            if not widget:
                continue

            uuid_str = self.id_controller.clean_uuid(getattr(widget, 'uuid', ''))
            rect = sub_window.geometry()
            is_maximized = bool(sub_window.windowState() & Qt.WindowState.WindowMaximized)

            positions[uuid_str] = {
                "rect": [rect.x(), rect.y(), rect.width(), rect.height()],
                "maximized": is_maximized
            }

        # Безопасно обновляем State
        if "workspace" not in self.state.project_data:
            self.state.project_data["workspace"] = {}

        self.state.project_data["workspace"]["mdi_positions"] = positions
        self.state.project_data["workspace"]["active_widget_uuid"] = active_uuid
        print("[DEBUG INTERFACE] Геометрия рабочего пространства успешно сохранена в State.")

    # =========================================================================
    # ПОЛНАЯ ПЕРЕСБОРКА ПОСЛЕ ЗАГРУЗКИ
    # =========================================================================

    def rebuild_interface(self):
        """
        Полностью пересобирает дерево проекта и восстанавливает окна MDI
        на основе актуального состояния в ProjectState.
        """
        sel_model = None
        if hasattr(self.win, 'tree_view') and self.win.tree_view:
            sel_model = self.win.tree_view.selectionModel()

        # Отключаем обновление интерфейса для предотвращения мерцания
        self.win.file_info.setUpdatesEnabled(False)

        # УДАЛЕНО: self.win.tree_model.blockSignals(True) <- Это ломало отрисовку!

        # Блокируем ТОЛЬКО модель выделения, чтобы HierarchyController не падал при очистке
        if sel_model:
            sel_model.blockSignals(True)

        try:
            # Очищаем старое дерево (метод clear сам безопасно уведомит View о сбросе)
            self.win.tree_model.clear()
            self.win.tree_model.setHorizontalHeaderLabels(["Project tree"])

            folder_items = {}
            hierarchy_list = self.state.project_data.get("hierarchy") or []

            # 1. Восстанавливаем папки
            for folder_data in hierarchy_list:
                folder_data = folder_data or {}
                uuid_str = folder_data.get("uuid")
                text = folder_data.get("text", "Folder")

                if not uuid_str:
                    continue

                folder_item = QStandardItem(text)
                folder_item.setData(uuid_str, Qt.ItemDataRole.UserRole)
                self.win.tree_model.appendRow(folder_item)
                folder_items[uuid_str] = folder_item

            # 2. Восстанавливаем виджеты внутри папок
            widgets_dict = self.state.project_data.get("widgets") or {}

            for w_uuid, descriptor in widgets_dict.items():
                descriptor = descriptor or {}
                parent_uuid = descriptor.get("parent_block_uuid")
                parent_folder_item = folder_items.get(parent_uuid)

                if parent_folder_item:
                    # Фабрика создаст окно и добавит дочерний элемент в дерево
                    self.win.widget_factory.restore_window_from_descriptor(descriptor, parent_folder_item)

        finally:
            # УДАЛЕНО: self.win.tree_model.blockSignals(False)

            # Разблокируем модель выделения обратно
            if sel_model:
                sel_model.blockSignals(False)
            self.win.file_info.setUpdatesEnabled(True)

        # 3. Восстанавливаем геометрию окон в QMdiArea
        if hasattr(self, '_restore_workspace_geometry'):
            self._restore_workspace_geometry()

    # =========================================================================
    # ВНУТРЕННИЕ МЕТОДЫ СБОРКИ
    # =========================================================================

    def _reconstruct_ui_layer(self, node_data: dict, parent_item):
        """Рекурсивный обход древовидной структуры метаданных (Перенесено из Lifecycle)."""
        if not node_data:
            return

        uuid_str = self.id_controller.clean_uuid(node_data.get("uuid"))
        name = node_data.get("text", "Unnamed Node")
        node_type = node_data.get("type")

        if not uuid_str:
            return

        if node_type == "root":
            for child_node in node_data.get("children", []):
                self._reconstruct_ui_layer(child_node, parent_item)
            return

        current_item = None

        if node_type == "folder":
            current_item = QStandardItem(name)
            current_item.setData(uuid_str, Qt.ItemDataRole.UserRole)
            parent_item.appendRow(current_item)

        elif node_type in ["gallery", "table", "graph"]:
            descriptor = self.state.get_widget_descriptor(uuid_str)
            if descriptor:
                # Фабрика создает окно, но позицию пока не меняет
                self.factory.restore_window_from_descriptor(descriptor, parent_item)

                # Ищем только что созданный элемент, чтобы прикрепить к нему детей, если есть
                if hasattr(self.win, 'hierarchy_controller'):
                    current_item = self.win.hierarchy_controller.find_item_by_uuid(uuid_str)

        next_parent = current_item if current_item else parent_item
        for child_node in node_data.get("children", []):
            self._reconstruct_ui_layer(child_node, next_parent)

    def _restore_workspace_geometry(self):
        """Применяет сохраненную геометрию, открывает окна текущей папки и фокусирует дерево."""
        print("\n[DEBUG INTERFACE] >>> Запуск финального восстановления интерфейса")
        workspace = self.state.project_data.get("workspace", {})
        positions = workspace.get("mdi_positions", {})
        active_uuid = self.id_controller.clean_uuid(workspace.get("active_widget_uuid"))

        mdi_area = getattr(self.win, 'widgets_area', None)
        if not mdi_area:
            return

        sub_windows = mdi_area.subWindowList()
        target_active_sub = None

        # Шаг 1: Находим UUID родительской папки для активного виджета из состояния
        widgets_dict = self.state.project_data.get("widgets", {})
        active_descriptor = widgets_dict.get(active_uuid) or {}
        # Фабрика сохраняет связь в parent_block_uuid
        target_folder_uuid = self.id_controller.clean_uuid(active_descriptor.get("parent_block_uuid", ""))

        print(f"  - Активный виджет: {active_uuid}, Его папка: {target_folder_uuid}")

        # Шаг 2: Проходим по всем окнам MDI
        for sub_window in sub_windows:
            widget = sub_window.widget()
            if not widget:
                continue

            uuid_str = self.id_controller.clean_uuid(getattr(widget, 'uuid', ''))
            # В фабрике вы передаете parent_block_uuid в параметр 'linked' окна
            folder_uuid = self.id_controller.clean_uuid(getattr(widget, 'linked', ''))

            # --- ПРИМЕНЕНИЕ ГЕОМЕТРИИ (используем ключи rect и maximized) ---
            geom_data = positions.get(uuid_str)
            if geom_data:
                rect_data = geom_data.get("rect")
                if rect_data and len(rect_data) == 4:
                    w, h = max(100, rect_data[2]), max(100, rect_data[3])
                    sub_window.setGeometry(QRect(rect_data[0], rect_data[1], w, h))

                if geom_data.get("maximized"):
                    sub_window.setWindowState(Qt.WindowState.WindowMaximized)
            # -----------------------------------------------------------------

            # КРИТИЧЕСКИЙ ВЫЗОВ: Если виджет находится в той же папке, что и активный — показываем его окно!
            if target_folder_uuid and folder_uuid == target_folder_uuid:
                sub_window.show()

            if uuid_str == active_uuid:
                target_active_sub = sub_window

        # Шаг 3: Активируем главное окно
        if target_active_sub:
            print(f"  - Активируем окно на переднем плане: '{target_active_sub.windowTitle()}'")
            mdi_area.setActiveSubWindow(target_active_sub)
            target_active_sub.show()

        # Шаг 4: Синхронизируем дерево проекта (передаем точное управление)
        if active_uuid:
            self._select_item_in_tree_by_uuid(active_uuid)

        print("[DEBUG INTERFACE] <<< Завершение работы восстановления интерфейса\n")

    def _select_item_in_tree_by_uuid(self, uuid_str):
        """
        Рекурсивно ищет элемент с указанным UUID в дереве проекта file_info
        и программно выделяет его.
        """
        model = getattr(self.win, 'tree_model', None)
        # Исправлено: берем строго file_info из MainWindow
        tree_view = getattr(self.win, 'file_info', None)

        if not model or not tree_view:
            print(f"[DEBUG INTERFACE] Ошибка: не удалось найти tree_model или file_info в MainWindow.")
            return

        def search_recursive(parent_item):
            for row in range(parent_item.rowCount()):
                child = parent_item.child(row)
                if child:
                    # В фабрике на строке 182 вы делаете: item.setData(widget_uuid, Qt.ItemDataRole.UserRole)
                    child_uuid = self.id_controller.clean_uuid(child.data(Qt.ItemDataRole.UserRole))
                    if child_uuid == uuid_str:
                        return child

                    found = search_recursive(child)
                    if found:
                        return found
            return None

        print(f"  - Поиск виджета {uuid_str} в дереве file_info...")
        target_item = search_recursive(model.invisibleRootItem())

        if target_item:
            index = target_item.index()
            # Выделяем элемент программно
            tree_view.setCurrentIndex(index)
            # Прокручиваем дерево к нему
            tree_view.scrollTo(index)
            print(f"  - [Успех] Элемент дерева '{target_item.text()}' успешно выбран.")
        else:
            print(f"  - [Внимание] Виджет с UUID {uuid_str} не найден в структуре tree_model.")

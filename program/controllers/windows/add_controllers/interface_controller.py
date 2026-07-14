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
        """Применяет сохраненную геометрию и фокус с подробной отладкой."""
        print("\n[DEBUG INTERFACE] >>> Запуск финального восстановления интерфейса")

        workspace = self.state.project_data.get("workspace", {})
        raw_active_uuid = workspace.get("active_widget_uuid")

        # Обязательно очищаем UUID, как мы делали это ранее для безопасности типов
        active_uuid = self.id_controller.clean_uuid(raw_active_uuid) if hasattr(self,
                                                                                'id_controller') else raw_active_uuid

        print(f"  - Ожидаемый активный UUID из файла: {active_uuid}")

        mdi_area = getattr(self.win, 'widgets_area', None)
        if not mdi_area:
            print("  - [CRITICAL] Не найден widgets_area в главном окне!")
            return

        sub_windows = mdi_area.subWindowList()
        print(f"  - Количество окон, зарегистрированных в QMdiArea прямо сейчас: {len(sub_windows)}")

        target_active_sub = None

        if active_uuid:
            for sub_window in sub_windows:
                widget = sub_window.widget()
                uuid_str = str(getattr(widget, 'uuid', ''))
                # Если id_controller доступен, лучше использовать его для очистки uuid_str
                if hasattr(self, 'id_controller'):
                    uuid_str = self.id_controller.clean_uuid(uuid_str)

                print(
                    f"    * Проверяем живое окно MDI: '{sub_window.windowTitle()}' | UUID: {uuid_str} | Видимость: {sub_window.isVisible()}")

                if uuid_str == active_uuid:
                    target_active_sub = sub_window
                    print(f"      -> Матч! Это окно должно стать активным.")
                    break

        if target_active_sub:
            print(f"  - Активируем окно: '{target_active_sub.windowTitle()}'")
            mdi_area.setActiveSubWindow(target_active_sub)
            target_active_sub.show()

            # Если у тебя есть метод программного выделения конкретного виджета в дереве, вызываем его здесь:
            if hasattr(self, '_select_item_in_tree_by_uuid'):
                self._select_item_in_tree_by_uuid(active_uuid)

        else:
            print("  - [WARN] Окно с active_uuid не найдено. Включаем отображение ПЕРВОЙ ПАПКИ (Fallback).")
            # ФОЛЛБЭК: Если виджет не найден или active_uuid пуст, выделяем первую папку
            if hasattr(self.win, 'hierarchy_controller'):
                self.win.hierarchy_controller.ensure_active_folder_selection()

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

    def remove_item_from_tree_by_uuid(self, uuid_str: str) -> bool:
        """
        Рекурсивно ищет элемент в дереве проекта по его UUID
        и удаляет его из отображения (ФИКС КРЕСТИКА ОКНА).
        """
        # Предполагаем, что модель дерева лежит в self.win.tree_model или self.tree_model
        model = getattr(self.win, 'tree_model', None)
        if not model:
            print("[TREE SYNC ERROR] Не найдена модель дерева проекта.")
            return False

        uuid_str = str(uuid_str).strip().lower()

        def find_and_remove(parent_item):
            for row in range(parent_item.rowCount()):
                child = parent_item.child(row)
                if child:
                    # Вытаскиваем UUID, который мы сохраняли в UserRole при построении
                    item_uuid = str(child.data(Qt.ItemDataRole.UserRole)).strip().lower()

                    if item_uuid == uuid_str:
                        print(f"[TREE SYNC] Элемент {uuid_str} найден в дереве. Удаляем строку {row}.")
                        parent_item.removeRow(row)
                        return True

                    # Рекурсивный спуск в подпапки
                    if find_and_remove(child):
                        return True
            return False

        # Блокируем сигналы на время удаления, чтобы избежать гонки перерисовок
        model.blockSignals(True)
        try:
            success = find_and_remove(model.invisibleRootItem())
        finally:
            model.blockSignals(False)

        if success:
            # Принудительно уведомляем QTreeView, что вид поменялся
            if hasattr(self.win, 'tree_view'):
                self.win.tree_view.update()
        return success

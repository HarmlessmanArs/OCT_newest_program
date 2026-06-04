import re
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

            if hasattr(self.win, 'runtime_registry') and hasattr(self.win.runtime_registry, 'clear_all'):
                self.win.runtime_registry.clear_all()

            # === ЭТАП 2: ВОССТАНОВЛЕНИЕ ИЕРАРХИИ И ГЕНЕРАЦИЯ ОКОН ===
            # Используем безопасную рекурсивную сборку
            tree_data = self.state.project_data.get('tree_structure', {})
            if not tree_data:
                self.win.statusBar().showMessage("Открыт пустой проект", 5000)
                return

            self._reconstruct_ui_layer(tree_data, self.win.tree_model.invisibleRootItem())

            # === ЭТАП 3: ФИНАЛИЗАЦИЯ И ГЕОМЕТРИЯ ===
            self.win.file_info.expandAll()

            if hasattr(self.win, 'update_window_title'):
                self.win.update_window_title()

            self._restore_workspace_geometry()
            self.win.statusBar().showMessage("Интерфейс успешно восстановлен", 5000)
            self._debug_print_tree_state()

        except Exception as e:
            self.win.statusBar().showMessage("Ошибка при сборке интерфейса", 5000)
            import traceback
            traceback.print_exc()

        finally:
            # Гарантированное снятие блокировок
            self.win.file_info.blockSignals(False)
            self.win.widgets_area.blockSignals(False)
            self.win.tree_model.blockSignals(False)

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
        positions = workspace.get("mdi_positions", {})
        active_uuid = self.id_controller.clean_uuid(workspace.get("active_widget_uuid"))

        mdi_area = getattr(self.win, 'widgets_area', None)
        if not mdi_area:
            return

        sub_windows = mdi_area.subWindowList()
        target_active_sub = None

        for sub_window in sub_windows:
            widget = sub_window.widget()
            uuid_str = self.id_controller.clean_uuid(getattr(widget, 'uuid', ''))

            # --- ПРИМЕНЕНИЕ ГЕОМЕТРИИ ---
            geom_data = positions.get(uuid_str)
            if geom_data:
                rect_data = geom_data.get("rect")
                if rect_data and len(rect_data) == 4:
                    # Защита от нулевых размеров
                    w, h = max(100, rect_data[2]), max(100, rect_data[3])
                    sub_window.setGeometry(QRect(rect_data[0], rect_data[1], w, h))

                if geom_data.get("maximized"):
                    sub_window.setWindowState(Qt.WindowState.WindowMaximized)
            # ----------------------------

            if uuid_str == active_uuid:
                target_active_sub = sub_window

        # Возвращаем фокус активному окну
        if target_active_sub:
            print(f"  - Активируем окно: '{target_active_sub.windowTitle()}'")
            mdi_area.setActiveSubWindow(target_active_sub)
            target_active_sub.show()
        print("[DEBUG INTERFACE] <<< Завершение работы восстановления интерфейса\n")

    def _debug_print_tree_state(self):
        # Твой старый отладочный вывод (без изменений)
        pass
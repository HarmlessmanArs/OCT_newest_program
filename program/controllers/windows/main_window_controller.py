from PyQt6 import QtWidgets
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QAction
from PyQt6.QtCore import Qt

from ...gui.windows import Ui_MainWindow
from ...state.project_state.state import ProjectState

# Импортируем контроллеры
from .add_controllers.project_io_controller import ProjectIOController
from .add_controllers.widget_factory_controller import WidgetFactoryController
from .add_controllers.hierarchy_controller import HierarchyController


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # 1. Системные переменные приложения
        self.app_name = 'OCT project'
        self.folder_count = 1
        self.gallery_count = 1
        self.graph_count = 1
        self.table_count = 1

        # 2. Инициализация State и реакция на него
        self.project_state = ProjectState()
        self.project_state.sig_modified_changed.connect(self._update_window_title)
        self.project_state.sig_project_path_changed.connect(self._update_window_title)
        self.project_state.sig_data_reset.connect(self._on_project_reset)

        # 3. Настройка компонентов дерева (Паттерн Model/View)
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Project tree"])
        self.file_info.setModel(self.tree_model)

        # 4. ВНЕДРЕНИЕ КОНТРОЛЛЕРОВ
        self.io_controller = ProjectIOController(self, self.project_state)
        self.widget_factory = WidgetFactoryController(self, self.project_state)
        self.hierarchy_controller = HierarchyController(self, self.project_state)

        # 5. Хоткеи и периферия интерфейса
        self._setup_shortcuts()

        # 6. Стартовое состояние (Создаем "Folder 0" через фабрику)
        # init_folder = self.widget_factory.create_folder("Folder 0")
        # self.file_info.setCurrentIndex(self.tree_model.indexFromItem(init_folder))
        # self._update_window_title()
        self._on_project_reset()

    def _setup_shortcuts(self):
        """Вынесенная настройка клавиатурных сокращений."""
        self.delete_action = QAction(self)
        self.delete_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self.delete_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.delete_action.triggered.connect(self.hierarchy_controller.on_delete_shortcut_triggered)
        self.file_info.addAction(self.delete_action)

    def _update_window_title(self):
        path = self.project_state.current_path
        project_name = path.name if path else "New project"
        marker = " *" if self.project_state.modified else ""
        self.setWindowTitle(f"[{project_name}]{marker} — {self.app_name}")

    def _clear_mdi_area_safely(self):
        """
        Безопасно уничтожает MDI окна, временно отключая сигналы закрытия,
        чтобы предотвратить лавинообразные рекурсивные вызовы в контроллерах.
        """
        for sub_window in self.widgets_area.subWindowList():
            widget = sub_window.widget()
            if widget and hasattr(widget, 'window_closed'):
                try:
                    # Отключаем обработчики, чтобы контроллеры не паниковали при зачистке
                    widget.window_closed.disconnect()
                except TypeError:
                    pass  # Сигнал не был подключен, игнорируем

            sub_window.close()
            sub_window.deleteLater()

    def _on_project_reset(self):
        """Вызывается при полной очистке/создании нового проекта."""
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Project Files"])

        # Безопасная очистка окон
        self._clear_mdi_area_safely()

        self.folder_count = 1
        self.gallery_count = 1
        self.graph_count = 1
        self.table_count = 1

        # ==================== ИСПРАВЛЕНИЕ ТУТ ====================
        # Создаем Folder 0 ТОЛЬКО если в состоянии проекта вообще нет папок (проект чистый)
        if not self.project_state.project_data.get("hierarchy"):
            init_folder = self.widget_factory.create_folder("Folder 0")
            self.file_info.setCurrentIndex(self.tree_model.indexFromItem(init_folder))

    def rebuild_interface(self):
        """
        Полная пересборка графического интерфейса на основе паттерна Model/View.
        Синхронизирует QTreeView и QMdiArea с актуальным состоянием self.project_state.project_data
        """
        self.statusBar().showMessage("Обновление интерфейса...")

        # Блокируем сигналы самого View и MDI-зоны на время жесткой перестройки
        self.file_info.blockSignals(True)
        self.widgets_area.blockSignals(True)

        try:
            # 1. Очищаем старую визуальную модель дерева
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels(["Project Files"])

            # 2. Безопасно уничтожаем окна без вызова побочных эффектов
            self._clear_mdi_area_safely()

            # 3. Извлекаем плоскую структуру проекта из синхронизированного State
            project_data = self.project_state.project_data
            hierarchy = project_data.get('hierarchy', [])

            if not hierarchy:
                self.statusBar().showMessage("Открыт пустой проект", 5000)
                return

            # 4. Строим карту связей "родитель -> список детей" для быстрого рекурсивного построения
            from collections import defaultdict
            parent_to_children = defaultdict(list)

            # Собираем все существующие UUID, чтобы отлавливать "сирот"
            all_uuids = {node.get('uuid') for node in hierarchy if node.get('uuid')}

            for node in hierarchy:
                p_uuid = node.get('parent_uuid')
                # Если parent_uuid не задан или родителя физически нет в проекте,
                # считаем элемент корневым (привязываем к коренному значению None)
                if p_uuid is None or p_uuid not in all_uuids:
                    parent_to_children[None].append(node)
                else:
                    parent_to_children[p_uuid].append(node)

            # 5. Запускаем построение дерева с корня (у которого parent_uuid = None)
            root_item = self.tree_model.invisibleRootItem()
            self._build_tree_nodes_from_hierarchy(root_item, None, parent_to_children)

            # Раскрываем все узлы дерева
            self.file_info.expandAll()

            # 6. Обновляем заголовок окна
            self._update_window_title()
            self.statusBar().showMessage("Интерфейс успешно восстановлен", 5000)

        except Exception as e:
            self.statusBar().showMessage("Ошибка при сборке интерфейса", 5000)
            raise RuntimeError(f"Сбой rebuild_interface: {str(e)}")

        finally:
            # Гарантированно возвращаем обработку сигналов интерфейсу
            self.file_info.blockSignals(False)
            self.widgets_area.blockSignals(False)

    def _build_tree_nodes_from_hierarchy(self, parent_item, parent_uuid, parent_to_children):
        """
        Рекурсивно строит иерархию интерфейса на основе плоской карты связей.
        Разделяет папки и функциональные окна анализа.
        """
        # Достаем список детей для текущего родительского UUID
        children = parent_to_children.get(parent_uuid, [])

        for child in children:
            node_uuid = child.get('uuid')
            node_text = child.get('text', 'Без названия')
            node_type = child.get('type')

            # Сценарий 1: Если узел является ПАПКОЙ
            if node_type == 'folder':
                tree_item = QStandardItem(node_text)
                if node_uuid:
                    tree_item.setData(node_uuid, Qt.ItemDataRole.UserRole)

                parent_item.appendRow(tree_item)

                # Рекурсивно уходим вглубь, чтобы построить детей внутри этой папки
                self._build_tree_nodes_from_hierarchy(tree_item, node_uuid, parent_to_children)

            # Сценарий 2: Если узел является ОКНОМ анализа (виджетом)
            else:
                widgets_dict = self.project_state.project_data.get("widgets", {})
                descriptor = widgets_dict.get(node_uuid)

                if descriptor:
                    # Фабрика сама создаст и окно, и элемент дерева QStandardItem,
                    # и правильно свяжет их с Single Source of Truth!
                    self.widget_factory.restore_window_from_descriptor(descriptor, parent_item)
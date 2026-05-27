from PyQt6 import QtWidgets, QtCore
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
        self.tree_model.setHorizontalHeaderLabels(["Project Files"])
        self.file_info.setModel(self.tree_model)

        # 4. ВНЕДРЕНИЕ КОНТРОЛЛЕРОВ
        self.io_controller = ProjectIOController(self, self.project_state)
        self.widget_factory = WidgetFactoryController(self, self.project_state)
        self.hierarchy_controller = HierarchyController(self, self.project_state)

        # 5. Хоткеи и периферия интерфейса
        self._setup_shortcuts()

        # 6. Стартовое состояние (Создаем "Folder 0" через фабрику)
        init_folder = self.widget_factory.create_folder("Folder 0")
        self.file_info.setCurrentIndex(self.tree_model.indexFromItem(init_folder))
        self._update_window_title()

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

    def _on_project_reset(self):
        """Вызывается при полной очистке/создании нового проекта."""
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Project Files"])

        for sub_window in self.widgets_area.subWindowList():
            sub_window.close()
            sub_window.deleteLater()

        self.folder_count = 1
        self.gallery_count = 1
        self.graph_count = 1
        self.table_count = 1

        init_folder = self.widget_factory.create_folder("Folder 0")
        self.file_info.setCurrentIndex(self.tree_model.indexFromItem(init_folder))

    def rebuild_interface(self):
        """
        Полная пересборка графического интерфейса на основе паттерна Model/View.
        Синхронизирует QTreeView и QMdiArea с актуальным состоянием self.project_state.project_data
        """
        self.statusBar().showMessage("Обновление интерфейса...")

        # 1. Блокируем сигналы представления на время пересборки модели
        self.file_info.blockSignals(True)

        try:
            # 2. Очищаем старую модель дерева
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels(["Project Files"])

            # 3. Безопасно уничтожаем все старые окна в MDI-зоне
            for sub_window in self.widgets_area.subWindowList():
                sub_window.close()
                sub_window.deleteLater()

            # 4. Очищаем центральный словарь тегов в CONSTANTS (если используете)
            # CONSTANTS.TAG_DICTIONARY.clear()

            # 5. Извлекаем структуру проекта из синхронизированного State
            project_data = self.project_state.project_data
            tree_structure = project_data.get('tree_structure', {})

            if not tree_structure:
                self.statusBar().showMessage("Открыт пустой проект", 5000)
                return

            # 6. Запускаем рекурсивное построение через QStandardItem
            root_item = self.tree_model.invisibleRootItem()
            self._build_tree_nodes_recursive(root_item, tree_structure)

            # Раскрываем все узлы дерева (у QTreeView этот метод вызывается на самом View)
            self.file_info.expandAll()

            # 7. Обновляем заголовок окна
            self._update_window_title()
            self.statusBar().showMessage("Интерфейс успешно восстановлен", 5000)

        except Exception as e:
            self.statusBar().showMessage("Ошибка при сборке интерфейса", 5000)
            raise RuntimeError(f"Сбой rebuild_interface: {str(e)}")

        finally:
            # Гарантированно возвращаем обработку сигналов представлению
            self.file_info.blockSignals(False)

    def _build_tree_nodes_recursive(self, parent_item, nodes_data: list | dict):
        """
        Рекурсивно обходит структуру tree_structure и наполняет QStandardItemModel.
        """
        items_list = nodes_data if isinstance(nodes_data, list) else nodes_data.get('children', [])

        if not items_list:
            if isinstance(nodes_data, dict) and 'text' in nodes_data:
                items_list = [nodes_data]
            else:
                return

        for item_data in items_list:
            node_text = item_data.get('text', 'Без названия')

            # Создаем элемент модели QStandardItem вместо QTreeWidgetItem
            tree_item = QStandardItem(node_text)

            # Извлекаем восстановленный QUuid
            node_uuid = item_data.get('uuid')

            if node_uuid:
                # Кладем QUuid в UserRole (работает идентично для всех элементов Qt)
                tree_item.setData(node_uuid, Qt.ItemDataRole.UserRole)

                # РЕГИСТРАЦИЯ В СИСТЕМЕ ТЕГОВ:
                # CONSTANTS.TAG_DICTIONARY[node_uuid] = tree_item

            # Добавляем созданный элемент к текущему родителю
            parent_item.appendRow(tree_item)

            # Рекурсивный спуск к дочерним элементам
            if 'children' in item_data:
                self._build_tree_nodes_recursive(tree_item, item_data['children'])
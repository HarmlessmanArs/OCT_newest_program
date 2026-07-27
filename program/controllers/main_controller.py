# program/controllers/main_controller.py
from PyQt6.QtWidgets import QMainWindow, QMdiSubWindow, QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from ..gui.windows.ui_main_window import Ui_MainWindow
from ..core.events import bus
from ..core.state import state
from .tree_controller import TreeController


class MainController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Словарь открытых окон {uid: QMdiSubWindow}
        self.active_mdi_windows = {}

        self._setup_ui()
        self._setup_connections()
        self._subscribe_to_events()

        # ИСПРАВЛЕНИЕ 2 и 5: Принудительно стартуем чистый проект при запуске программы!
        self.on_new_project()

    def _setup_ui(self):
        """Настройка дополнительных элементов UI"""
        # --- Инициализация нашего нового контроллера дерева ---
        self.tree_controller = TreeController(self.ui.file_info)

        # --- Скрывающаяся боковая панель (file_info) ---
        self.toggle_sidebar_action = QAction("Show/Hide Explorer", self)

        # --- Скрывающаяся боковая панель (file_info) ---
        self.toggle_sidebar_action = QAction("Show/Hide Explorer", self)
        self.toggle_sidebar_action.setShortcut("Ctrl+B")
        self.toggle_sidebar_action.triggered.connect(self.toggle_sidebar)
        self.addAction(self.toggle_sidebar_action)
        self.ui.menuFile.addAction(self.toggle_sidebar_action)

        # --- Контекстное меню для MDI-области (ПКМ) ---
        self.ui.widgets_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.widgets_area.customContextMenuRequested.connect(self._show_mdi_context_menu)

    def toggle_sidebar(self):
        """Показывает или скрывает QTreeView (file_info)"""
        is_visible = self.ui.file_info.isVisible()
        self.ui.file_info.setVisible(not is_visible)

    def _setup_connections(self):
        """Подключение кнопок из menubar к методам"""
        # Меню File
        self.ui.actionNew.triggered.connect(self.on_new_project)
        # Заглушки для будущего:
        # self.ui.actionOpen_project.triggered.connect(self.on_open_project)
        # self.ui.actionSave_project.triggered.connect(self.on_save_project)
        self.ui.actionQuit.triggered.connect(self.close)

        # Меню Instruments (Пример, как запрашивать создание галереи)
        self.ui.actionCreate_new_gallery.triggered.connect(self.on_create_gallery)

    def _subscribe_to_events(self):
        """Подписка на глобальную шину событий"""
        bus.request_open_widget.connect(self._handle_open_widget)
        bus.node_removed.connect(self._handle_node_removed)
        bus.project_modified.connect(self._update_window_title)
        bus.active_widget_changed.connect(self._handle_active_widget_changed)

    # --- Обработчики действий меню ---

    def on_new_project(self):
        """Сброс состояния при создании нового проекта"""
        # ИСПРАВЛЕНИЕ 3: Очищаем визуальные MDI-окна от старого проекта
        for window in self.active_mdi_windows.values():
            window.close()
            window.deleteLater()
        self.active_mdi_windows.clear()

        # Сбрасываем ядро (оно само создаст папку Dataset 1)
        state.reset()

        # ИСПРАВЛЕНИЕ 5: Обновляем заголовок на [New Project] при сбросе
        self._update_window_title(False)

    def on_create_gallery(self):
        """Создание новой пустой галереи внутри выбранной папки"""
        parent_uid = None

        # 1. Пытаемся получить выделенный элемент из дерева
        selection = self.ui.file_info.selectionModel().selectedIndexes()
        if selection:
            index = selection[0]
            item = self.tree_controller.model.itemFromIndex(index)
            selected_uid = item.data(Qt.ItemDataRole.UserRole)

            node = state.get_node(selected_uid)
            if node:
                # Если выбрали саму папку - кладем в нее. Если выбрали другую галерею - кладем в ее родителя
                parent_uid = node.uid if node.node_type == "folder" else node.parent_uid

        # 2. Если ничего не выделено (или сняли выделение), берем самую первую папку проекта
        if not parent_uid:
            folders = [uid for uid, n in state.nodes.items() if n.node_type == "folder"]
            if folders:
                parent_uid = folders[0]
            else:
                # На крайний случай, если папок вообще нет, создаем новую
                new_folder = state.add_node(name="Dataset", node_type="folder")
                parent_uid = new_folder.uid

        # 3. Создаем галерею, надежно привязанную к родителю
        new_node = state.add_node(name="New Gallery", node_type="gallery", parent_uid=parent_uid)

        # 4. Сразу открываем виджет после создания
        bus.request_open_widget.emit(new_node.uid)

    def _update_window_title(self, is_modified: bool):
        """Обновление заголовка с правильной обработкой [*]"""
        # Берем имя проекта из state (по умолчанию там "[New Project]")
        project_name = state.filepath if state.filepath else "[New Project]"

        # ИСПРАВЛЕНИЕ 4: Правильный механизм Qt для отображения несохраненных изменений.
        # Qt сам покажет или скроет [*] в зависимости от setWindowModified.
        self.setWindowTitle(f"OCT Image Processing - {project_name}[*]")
        self.setWindowModified(is_modified)

    def _show_mdi_context_menu(self, pos):
        """Создает и показывает меню по правому клику в MDI области"""
        context_menu = QMenu(self)

        action_new_folder = QAction("Create new folder", self)
        action_new_gallery = QAction("Create new gallery", self)

        # ИСПРАВЛЕНИЕ 1: Меняем имена методов на правильные, чтобы не было вылета (краша)
        action_new_folder.triggered.connect(self.on_create_folder)
        action_new_gallery.triggered.connect(self.on_create_gallery)

        context_menu.addAction(action_new_folder)
        context_menu.addAction(action_new_gallery)
        context_menu.exec(self.ui.widgets_area.mapToGlobal(pos))

    def on_create_folder(self):
        """Пользователь запросил создание новой папки"""
        state.add_node("Dataset", "folder")

    # --- Логика OriginPro (Скрытие/Показ MDI окон) ---

    def _update_mdi_visibility(self, active_folder_uid: str):
        """Оставляет видимыми только те окна, которые принадлежат к выбранной папке"""
        for uid, sub_window in self.active_mdi_windows.items():
            node = state.get_node(uid)
            if not node:
                continue

            if node.parent_uid == active_folder_uid:
                sub_window.show()
                # ВАЖНО: Вытаскиваем окно на передний план!
                sub_window.raise_()
                sub_window.activateWindow()
            else:
                sub_window.hide()

    def _handle_open_widget(self, node_uid: str):
        """Открытие MDI окна (когда мы кликаем по галерее в дереве)"""
        node = state.get_node(node_uid)
        if not node:
            return

        if node_uid in self.active_mdi_windows:
            sub = self.active_mdi_windows[node_uid]
            sub.show()
            sub.raise_()
            sub.activateWindow()
            sub.setFocus()
            return

        # ---- НОВЫЙ КОД ФАБРИКИ ----
        from program.gui.widgets.factory import WidgetFactory

        # Фабрика сама подберет нужный класс (GalleryWidget и т.д.)
        # и пробросит в него UID для связи с ядром
        widget = WidgetFactory.create(node.node_type, node.uid)

        # Добавляем готовый виджет со всем интерфейсом в MDI-зону
        sub_window = self.ui.widgets_area.addSubWindow(widget)

        # MDI-окно должно быть чуть больше виджета внутри, чтобы вместить рамки
        sub_window.resize(widget.minimumSize().width() + 20,
                          widget.minimumSize().height() + 40)

        sub_window.setWindowTitle(node.name)
        sub_window.show()

        self.active_mdi_windows[node_uid] = sub_window

    def _handle_active_widget_changed(self, uid: str):
        """Обработка одинарного клика в дереве для фильтрации окон"""
        node = state.get_node(uid)
        if not node:
            return
        # Если кликнули на папку - показываем её окна
        if node.node_type == "folder":
            self._update_mdi_visibility(uid)
        # Если кликнули на галерею/график - показываем окна родительской папки
        elif node.parent_uid:
            self._update_mdi_visibility(node.parent_uid)

    def _handle_node_removed(self, node_uid: str):
        """Гарантированное уничтожение MDI окна при удалении узла (Багфикс)"""
        if node_uid in self.active_mdi_windows:
            sub_window = self.active_mdi_windows.pop(node_uid)
            sub_window.close()
            sub_window.deleteLater()
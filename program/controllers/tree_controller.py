# program/controllers/tree_controller.py
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtWidgets import QTreeView, QStyle, QHeaderView

from program.core.state import state
from program.core.events import bus


class TreeController:
    """Контроллер для управления QTreeView через паттерн MVC"""

    def __init__(self, tree_view: QTreeView):
        self.tree = tree_view

        # Создаем модель данных
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Project Explorer"])
        self.tree.setModel(self.model)

        # Включаем ползунок, если содержимое выходит за границы
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Отключаем сжатие колонки под размер окна
        self.tree.header().setStretchLastSection(False)

        # Заставляем столбец автоматически расширяться под длину текста
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        # Словарь для быстрого поиска визуальных элементов по UID
        # Формат: {uid: QStandardItem}
        self._items = {}

        self._subscribe_to_bus()
        self._setup_view_connections()

        self._populate_from_state()

    def _subscribe_to_bus(self):
        """Подписка на изменения данных из ProjectState"""
        bus.project_created.connect(self._on_project_created)
        bus.node_added.connect(self._on_node_added)
        bus.node_removed.connect(self._on_node_removed)
        bus.node_renamed.connect(self._on_node_renamed)
        bus.node_moved.connect(self._on_node_moved)

    # --- Обработчики событий шины (От State к UI) ---

    def _on_project_created(self):
        """Очистка дерева при создании нового проекта"""
        self.model.removeRows(0, self.model.rowCount())
        self._items.clear()

    def _setup_view_connections(self):
        """Подписка на действия пользователя в интерфейсе"""
        # Двойной клик — запрос на открытие окна
        self.tree.doubleClicked.connect(self._on_double_clicked)
        # Одинарный клик — обновление видимости окон
        self.tree.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # НОВОЕ: Подписка на переименование элемента пользователем
        self.model.itemChanged.connect(self._on_item_changed)

    def _on_node_added(self, uid: str):
        """Добавление нового узла в дерево"""
        node = state.get_node(uid)
        if not node:
            return

        item = QStandardItem(node.name)
        item.setData(uid, Qt.ItemDataRole.UserRole)
        # ИЗМЕНЕНО: Разрешаем переименование прямо в дереве
        item.setEditable(True)

        style = self.tree.style()
        if node.node_type == "folder":
            icon = style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        else:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        item.setIcon(icon)

        self._items[uid] = item

        if node.parent_uid and node.parent_uid in self._items:
            parent_item = self._items[node.parent_uid]
            parent_item.appendRow(item)
            self.tree.expand(parent_item.index())
        else:
            self.model.invisibleRootItem().appendRow(item)

    def _on_node_renamed(self, uid: str, new_name: str):
        """Обновление имени узла по сигналу из ядра"""
        if uid in self._items:
            item = self._items[uid]
            # ВАЖНО: Отключаем сигналы, чтобы не вызвать бесконечный цикл
            # (UI изменился -> Ядро -> UI изменился -> Ядро)
            self.model.blockSignals(True)
            item.setText(new_name)
            self.model.blockSignals(False)

    def _on_item_changed(self, item: QStandardItem):
        """Обработка переименования элемента пользователем"""
        uid = item.data(Qt.ItemDataRole.UserRole)
        new_name = item.text()

        node = state.get_node(uid)
        if node and node.name != new_name:
            # Отправляем новое имя в ядро, оно само подберет суффикс, если есть дубликат
            state.rename_node(uid, new_name)

    def select_node(self, uid: str):
        """Программное выделение узла (полезно при загрузке проекта)"""
        if uid in self._items:
            index = self._items[uid].index()
            self.tree.setCurrentIndex(index)

    def _on_node_removed(self, uid: str):
        """Удаление узла из дерева"""
        if uid not in self._items:
            return

        item = self._items.pop(uid)
        if item.parent():
            item.parent().removeRow(item.row())
        else:
            self.model.invisibleRootItem().removeRow(item.row())

    def _on_node_moved(self, uid: str, new_parent_uid: str):
        """Перемещение узла (задел для Drag & Drop)"""
        if uid not in self._items:
            return

        item = self._items[uid]

        # Извлекаем строку из старого родителя
        old_parent = item.parent()
        if old_parent:
            row_items = old_parent.takeRow(item.row())
        else:
            row_items = self.model.invisibleRootItem().takeRow(item.row())

        # Добавляем к новому родителю
        if new_parent_uid in self._items:
            self._items[new_parent_uid].appendRow(row_items)
            self.tree.expand(self._items[new_parent_uid].index())
        else:
            self.model.invisibleRootItem().appendRow(row_items)

    # --- Обработчики действий мыши (От UI к State/Bus) ---

    def _on_double_clicked(self, index: QModelIndex):
        """Когда пользователь дважды кликает по элементу"""
        item = self.model.itemFromIndex(index)
        if not item:
            return

        uid = item.data(Qt.ItemDataRole.UserRole)
        node = state.get_node(uid)

        # Если это не папка — просим главное окно открыть виджет
        if node and node.node_type != "folder":
            bus.request_open_widget.emit(uid)

    def _on_selection_changed(self, selected, deselected):
        """Когда пользователь просто выделяет элемент в дереве"""
        indexes = selected.indexes()
        if not indexes:
            return

        item = self.model.itemFromIndex(indexes[0])
        uid = item.data(Qt.ItemDataRole.UserRole)

        # Трубим в шину, что активный элемент изменился
        bus.active_widget_changed.emit(uid)

    def _populate_from_state(self):
        """Синхронизация дерева с текущим состоянием при старте приложения"""
        # Сначала отрисовываем все папки (чтобы родительские узлы гарантированно существовали)
        folders = [uid for uid, n in state.nodes.items() if n.node_type == "folder"]
        for uid in folders:
            if uid not in self._items:
                self._on_node_added(uid)

        # Затем отрисовываем всё остальное (галереи, таблицы и т.д.)
        files = [uid for uid, n in state.nodes.items() if n.node_type != "folder"]
        for uid in files:
            if uid not in self._items:
                self._on_node_added(uid)
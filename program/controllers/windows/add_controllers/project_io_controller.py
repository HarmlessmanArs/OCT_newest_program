from pathlib import Path
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import QObject, pyqtSlot
import pprint

from ....project_storage.io.saver import SaveProjectWorker
from ....project_storage.io.loader import LoadProjectWorker
from ....project_storage.io.reader import ProjectReader  # Импортируем ридер для переоткрытия файлов
from ....utils.types_restore import restore_snapshot_types


class ProjectIOController(QObject):
    """Отвечает за сохранение, создание нового проекта и загрузку данных."""

    def __init__(self, main_window, project_state):
        super().__init__(main_window)
        self.win = main_window
        self.state = project_state
        self.save_worker = None
        self.load_worker = None

        # Привязываем экшены меню
        if hasattr(self.win, 'actionSave_project'):
            self.win.actionSave_project.triggered.connect(self.on_save_project)
        if hasattr(self.win, 'actionSave_project_as'):
            self.win.actionSave_project_as.triggered.connect(self.on_save_project_as)
        if hasattr(self.win, 'actionOpen_project'):
            self.win.actionOpen_project.triggered.connect(self.on_open_project)
        if hasattr(self.win, 'actionNew'):
            self.win.actionNew.triggered.connect(self.on_new_project)

    @pyqtSlot()
    def on_save_project(self):
        if self.state.current_path is None:
            self.on_save_project_as()
        else:
            self._execute_background_save(self.state.current_path)

    @pyqtSlot()
    def on_save_project_as(self):
        default_name = "Default_project.bmip"
        start_dir = self.state.current_path.parent if self.state.current_path else self.state.user_settings.last_save_project_folder

        file_path_str, _ = QFileDialog.getSaveFileName(
            self.win, "Save project as...", str(start_dir / default_name), "BMIP Projects (*.bmip)"
        )
        if not file_path_str:
            return

        target_path = Path(file_path_str)
        if target_path.suffix != '.bmip':
            target_path = target_path.with_suffix('.bmip')

        self._execute_background_save(target_path)

    def _on_save_completed(self, success: bool, message: str, saved_path: Path):
        self._set_menu_enabled(True)

        if success:
            self.state.set_path(saved_path)
            self.state.set_modified(False)

            # Восстанавливаем блокировку: открываем новый Reader для сохраненного файла
            try:
                reader = ProjectReader(saved_path)
                reader.open()
                self.state.project_reader = reader
            except Exception as e:
                QMessageBox.warning(self.win, "Reader Error",
                                    f"Project saved, but failed to lock file for reading:\n{e}")

            self.win.statusBar().showMessage("Project completely saved", 5000)
        else:
            # Если сохранение упало, пытаемся вернуть ридер на старый файл, если он существовал
            if self.state.current_path and self.state.current_path.exists():
                try:
                    reader = ProjectReader(self.state.current_path)
                    reader.open()
                    self.state.project_reader = reader
                except:
                    pass
            QMessageBox.critical(self.win, "Saving Error", f"The file could not be saved:\n{message}")
            self.win.statusBar().showMessage("Saving Error", 5000)

    @pyqtSlot()
    def on_open_project(self):
        # 1. Проверяем, есть ли несохраненные изменения
        if getattr(self.state, 'modified', False):
            reply = QMessageBox.question(
                self.win,
                "Unsaved Changes",
                "The current project has unsaved changes. Are you sure you want to close it and load another one? All unsaved data will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            # Если пользователь нажал No, отменяем загрузку нового проекта
            if reply == QMessageBox.StandardButton.No:
                return

        # 2. Если сохранять не нужно (или согласились сбросить), открываем диалог загрузки
        start_dir = self.state.current_path.parent if self.state.current_path else self.state.user_settings.last_save_project_folder

        file_path_str, _ = QFileDialog.getOpenFileName(
            self.win, "Open project...", str(start_dir), "BMIP Projects (*.bmip);;All Files (*)"
        )
        if not file_path_str:
            return

        self._execute_background_load(Path(file_path_str))

    def _execute_background_load(self, path: Path):
        self._set_menu_enabled(False)
        self.win.statusBar().showMessage("Project loading...")

        self.load_worker = LoadProjectWorker(path)
        if hasattr(self.win, 'progressBar'):
            self.load_worker.progress.connect(self.win.progressBar.setValue)

        # ИСПРАВЛЕНО: Подключаемся к кастомному work_finished, а не к нативному finished
        self.load_worker.work_finished.connect(self._on_load_completed)
        self.load_worker.start()

    def _close_all_windows_silently(self):
        """Находит все MDI-окна и закрывает их без вызова QMessageBox."""
        mdi_area = getattr(self.win, 'mdi_area', getattr(self.win, 'mdiArea', None))
        if mdi_area:
            for window in mdi_area.subWindowList():
                widget = window.widget()
                if widget and hasattr(widget, '_force_close'):
                    widget._force_close = True
                window.close()

        # ==================== ИСПРАВЛЕНИЕ ЗДЕСЬ ====================
        # Очищаем реестр рантайма, чтобы он забыл UUID окон из старого проекта
        if hasattr(self.win, 'runtime_registry'):
            # Если у вашего класса реестра есть метод clear(), вызываем его:
            if hasattr(self.win.runtime_registry, 'clear'):
                self.win.runtime_registry.clear()
            # Если метода clear нет, но внутри используется словарь (например, self.windows), очищаем его напрямую:
            elif hasattr(self.win.runtime_registry, 'windows') and isinstance(self.win.runtime_registry.windows, dict):
                self.win.runtime_registry.windows.clear()
        # ===========================================================

    def _execute_background_save(self, path: Path):
        self._set_menu_enabled(False)
        self.win.statusBar().showMessage("Project saving...")
        if self.state.project_reader:
            self.state.project_reader.close()
            self.state.project_reader = None
        # ==================== НОВОЕ ====================
        # Синхронизируем интерфейс со State ПЕРЕД созданием слепка
        self._sync_workspace_geometry()
        # ===============================================
        snapshot = self.state.get_complete_snapshot()
        self.save_worker = SaveProjectWorker(path, snapshot)
        self.save_worker.work_finished.connect(lambda success, msg: self._on_save_completed(success, msg, path))
        self.save_worker.start()

    def _on_load_completed(self, success: bool, result, reader):
        self._set_menu_enabled(True)
        if hasattr(self.win, 'progressBar'):
            self.win.progressBar.setValue(0)

        if not success:
            QMessageBox.critical(self.win, "Loading Error", f"The file could not be loaded:\n{result}")
            self.win.statusBar().showMessage("Loading Error", 5000)
            return

        try:
            restored_snapshot = restore_snapshot_types(result)

            self._close_all_windows_silently()

            if hasattr(self.state, 'project_reader') and self.state.project_reader:
                try:
                    self.state.project_reader.close()
                except:
                    pass

            self.state.project_reader = reader

            self.state.hydrate_from_snapshot(restored_snapshot, reader)
            self.state.set_path(reader.file_path)
            self.state.set_modified(False)

            # self.state.sig_data_reset.emit()
            self.state.sig_project_loaded.emit()

            self.win.statusBar().showMessage("Project loaded completely", 5000)

        except Exception as e:
            if reader:
                reader.close()
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.win, "Deserialization Error", f"Failed to reconstruct project:\n{str(e)}")
            self.win.statusBar().showMessage("Loading Error", 5000)

    @pyqtSlot()
    def on_new_project(self):
        # Здесь тоже делаем проверку на сохранение, чтобы лишний раз не пугать пользователя,
        # если проект и так чистый или уже сохранен.
        if getattr(self.state, 'modified', False):
            reply = QMessageBox.question(
                self.win, "New project",
                "Current project has unsaved changes. Are you sure you want to create a new project? Unsaved data will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        self._close_all_windows_silently()

        if hasattr(self.state, 'project_reader') and self.state.project_reader:
            try:
                self.state.project_reader.close()
            except:
                pass
            self.state.project_reader = None

        self.state.reset_to_new()
        self.win.statusBar().showMessage("New project created", 5000)

    def _set_menu_enabled(self, enabled: bool):
        actions = ['actionSave_project', 'actionSave_project_as', 'actionOpen_project', 'actionNew_project']
        for action_name in actions:
            if hasattr(self.win, action_name):
                getattr(self.win, action_name).setEnabled(enabled)

    def _sync_workspace_geometry(self):
        """Собирает геометрию всех MDI-окон перед сохранением проекта."""
        positions = {}
        active_uuid = None

        mdi_area = getattr(self.win, 'widgets_area', None)
        if not mdi_area:
            return

        active_sub = mdi_area.activeSubWindow()

        for sub_window in mdi_area.subWindowList():
            widget = sub_window.widget()
            uuid_str = getattr(widget, 'uuid', None)

            if uuid_str:
                rect = sub_window.geometry()
                positions[str(uuid_str)] = {
                    "geometry": [rect.x(), rect.y(), rect.width(), rect.height()],  # Изменили ключ на 'geometry'
                    "is_maximized": sub_window.isMaximized()  # Изменили ключ на 'is_maximized'
                }

                if sub_window == active_sub:
                    active_uuid = str(uuid_str)

        self.state.update_workspace_state(active_uuid, positions)

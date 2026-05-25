from PyQt6.QtCore import Qt
from program.gui.windows import Ui_Form_table
from .widgets_controller import WidgetsWindow


class TableWindow(WidgetsWindow):

    def __init__(self, link_name, link_idx, obj_type='table', linked=None, parent=None):
        super().__init__(link_name, link_idx, obj_type, linked, parent)
        self.setWindowFlag(Qt.WindowType.Window)

        self.ui = Ui_Form_table()
        self.ui.setupUi(self)

        self.setWindowTitle(link_name)
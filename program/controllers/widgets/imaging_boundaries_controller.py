from PyQt6.QtCore import Qt
from program.gui.windows import Ui_Form_img_bound
from .widgets_controller import WidgetsWindow


class GraphWindow(WidgetsWindow):

    def __init__(self, link_name, link_idx, obj_type='imaging boundaries', linked=None, parent=None):
        super().__init__(link_name, link_idx, obj_type, linked, parent)
        self.setWindowFlag(Qt.WindowType.Window)

        self.ui = Ui_Form_img_bound()
        self.ui.setupUi(self)

        self.setWindowTitle(link_name)
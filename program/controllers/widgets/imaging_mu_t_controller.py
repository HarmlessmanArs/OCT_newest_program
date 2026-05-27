from PyQt6.QtCore import Qt
from program.gui.windows import Ui_Form_img_mu_t
from .widgets_controller import WidgetsWindow


class GraphWindow(WidgetsWindow):

    def __init__(self, link_name, link_idx, obj_type='imaging mu_t', state=None, linked=None, parent=None):
        super().__init__(link_name, link_idx, obj_type, state, linked, parent)
        self.setWindowFlag(Qt.WindowType.Window)

        self.ui = Ui_Form_img_mu_t()
        self.ui.setupUi(self)

        self.setWindowTitle(link_name)
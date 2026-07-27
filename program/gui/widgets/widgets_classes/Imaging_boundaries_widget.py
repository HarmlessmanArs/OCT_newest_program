from ..base_widget import BaseProjectWidget
from ...windows.ui_imaging_boundaries_window import Ui_Form_img_bound


class BoundariesWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_img_bound()
        self.ui.setupUi(self)
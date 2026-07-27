from ..base_widget import BaseProjectWidget
from ...windows.ui_imaging_roi_window import Ui_Form_img_roi


class RoiWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_img_roi()
        self.ui.setupUi(self)
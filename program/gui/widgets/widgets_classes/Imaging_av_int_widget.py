from ..base_widget import BaseProjectWidget
from ...windows.ui_imaging_av_int_window import Ui_Form_img_av_int


class IntensityWidget(BaseProjectWidget):
    def __init__(self, uid: str):
        super().__init__(uid)
        self.ui = Ui_Form_img_av_int()
        self.ui.setupUi(self)
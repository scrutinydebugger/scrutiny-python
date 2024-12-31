
from scrutiny.gui.themes import ScrutinyTheme, ScrutinyThemeProperties
from PySide6.QtGui import QColor

class DefaultTheme(ScrutinyTheme):

    pro_dict = {
        ScrutinyThemeProperties.CHART_NORMAL_SERIES_WIDTH : 2,
        ScrutinyThemeProperties.CHART_EMPHASIZED_SERIES_WIDTH : 3,
        ScrutinyThemeProperties.CHART_CALLOUT_MARKER_RADIUS : 5,
    }

    def get_val(self, prop:ScrutinyThemeProperties):
        return self.pro_dict[prop]
        

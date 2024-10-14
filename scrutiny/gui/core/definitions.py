__all__ = ['WidgetState']

import enum
from dataclasses import dataclass

class WidgetState:
    default = "default"
    error = "error"
    success = "success"
    warning = "warning"
    

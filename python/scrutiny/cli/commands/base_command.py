import argparse
from abc import ABC

class BaseCommand(ABC):

    @classmethod
    def get_name(cls):
        return cls._cmd_name_

    @classmethod
    def get_brief(cls):
        return cls._brief_

    @classmethod
    def get_group(cls):
        if hasattr(cls, '_group_'):
            return cls._group_
        else:
            return ''

    @classmethod
    def get_prog(cls):
        return 'scrutiny ' + cls.get_name()
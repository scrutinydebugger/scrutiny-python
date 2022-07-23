#    abstract_link.py
#        Base class for all device communication link (serial, udp, other)
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

LinkConfig = Dict[Any, Any]


class AbstractLink(ABC):

    @classmethod
    @abstractmethod
    def make(cls, config: LinkConfig) -> "AbstractLink":
        return cls(config)

    @abstractmethod
    def __init__(self, config: LinkConfig):
        pass

    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def initialized(self):
        pass

    @abstractmethod
    def destroy(self):
        pass

    @abstractmethod
    def write(self, data: bytes) -> None:
        pass

    @abstractmethod
    def read(self) -> Optional[bytes]:
        pass

    @abstractmethod
    def process(self):
        pass

    @abstractmethod
    def operational(self) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def validate_config(config: LinkConfig) -> None:
        pass

    @abstractmethod
    def get_config(self) -> LinkConfig:
        pass

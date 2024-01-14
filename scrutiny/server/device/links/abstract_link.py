#    abstract_link.py
#        Base class for all device communication link (serial, udp, other)
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

LinkConfig = Dict[str, Any]


class AbstractLink(ABC):

    @classmethod
    @abstractmethod
    def make(cls, config: LinkConfig) -> "AbstractLink":
        """Construct a Link object from its configuration"""
        return cls(config)

    @abstractmethod
    def __init__(self, config: LinkConfig):
        pass

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the communication channel. The channel is expected to be usable after this"""
        pass

    @abstractmethod
    def initialized(self) -> bool:
        """Returns True if the Link object has been initialized"""
        pass

    @abstractmethod
    def destroy(self) -> None:
        """Release all internal resources and put the Link into a non-usable state"""
        pass

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Write data into the communication channels"""
        pass

    @abstractmethod
    def read(self) -> Optional[bytes]:
        """Reads data from the communication channel. Returns None if not available"""
        pass

    @abstractmethod
    def process(self) -> None:
        """To be called periodically"""
        pass

    @abstractmethod
    def operational(self) -> bool:
        """Returns True if the communication channel is in a functional state"""
        pass

    @staticmethod
    @abstractmethod
    def validate_config(config: LinkConfig) -> None:
        """Raises an exception if the configuration is not good"""
        pass

    @abstractmethod
    def get_config(self) -> LinkConfig:
        """Get the link configuration"""
        pass

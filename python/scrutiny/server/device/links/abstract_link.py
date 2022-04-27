
from abc import ABC, abstractmethod
from typing import Optional, Dict

LinkConfig = Optional[Dict[str, str]]


class AbstractLink(ABC):

    @abstractmethod
    def __init__(self, config: LinkConfig):
        pass

    @abstractmethod
    def initialize(self):
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

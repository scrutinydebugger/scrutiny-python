#    abstract_client_handler.py
#        Base class for all API client handlers
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from abc import abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass

from .message_definitions import APIMessage

ClientHandlerConfig = Dict[str, str]


@dataclass
class ClientHandlerMessage:
    conn_id: str
    obj: APIMessage


class AbstractClientHandler:

    @abstractmethod
    def __init__(self, config: ClientHandlerConfig):
        pass

    @abstractmethod
    def send(self, msg: ClientHandlerMessage) -> None:
        pass

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def process(self) -> None:
        pass

    @abstractmethod
    def available(self) -> bool:
        pass

    @abstractmethod
    def recv(self) -> Optional[ClientHandlerMessage]:
        pass

    @abstractmethod
    def is_connection_active(self, conn_id: str) -> bool:
        pass
